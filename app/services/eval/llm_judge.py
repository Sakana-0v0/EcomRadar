"""LLM-as-Judge 评分器.

用 LLM 对生成结果打 1-5 分,适合:
- 开放式问答
- 摘要 / 报告
- 主观质量评估

评分维度:
- score: 1-5 整数
- reasoning: 评分理由
- criteria: 子维度分数字典 (correctness, completeness, etc.)

设计取舍:
- 解析容错: 即使 LLM 输出有 markdown 围栏或多余文字, 也能提取 JSON
- 默认值: 解析失败时返回 score=0 + 错误说明
- 可注入 LLM client: 测试可 mock
"""
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Awaitable, Callable, Optional


LLMCallFn = Callable[[str], Awaitable[str]]


@dataclass
class JudgeScore:
    """LLM 评分结果."""
    score: int
    reasoning: str
    criteria: dict = field(default_factory=dict)
    raw_output: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PROMPT = """你是一名严谨的评测专家。请根据参考答案, 对 AI 系统的回答打分(1-5 分)。

## 问题
{query}

## 参考答案
{reference}

## AI 回答
{prediction}

## 评分标准
- 5 分: 完全正确, 包含所有关键信息
- 4 分: 基本正确, 缺少 1-2 个非关键细节
- 3 分: 部分正确, 遗漏关键信息
- 2 分: 大部分错误, 仅有少量正确
- 1 分: 完全错误或答非所问

请严格按以下 JSON 格式输出 (不要有任何多余文字):

```json
{{
  "score": <1-5>,
  "reasoning": "<简短评分理由>",
  "criteria": {{
    "correctness": <0-1>,
    "completeness": <0-1>,
    "relevance": <0-1>
  }}
}}
```
"""


class LLMJudge:
    """LLM-as-Judge 评分器."""

    def __init__(
        self,
        llm_call_fn: Optional[LLMCallFn] = None,
        prompt_template: Optional[str] = None,
    ):
        """初始化.

        Args:
            llm_call_fn: 异步 LLM 调用函数. 默认为 LLM API 调用.
            prompt_template: 评分 prompt, 含 {query}/{reference}/{prediction} 占位符
        """
        self.llm_call_fn = llm_call_fn or self._default_llm_call
        self.prompt_template = prompt_template or DEFAULT_PROMPT

    async def _default_llm_call(self, prompt: str) -> str:
        """默认 LLM 调用 (httpx)."""
        import httpx
        from app.core.config import settings
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _build_prompt(self, query: str, prediction: str, reference: str) -> str:
        return self.prompt_template.format(
            query=query, reference=reference, prediction=prediction,
        )

    def _parse_output(self, llm_output: str) -> JudgeScore:
        """解析 LLM 输出为 JudgeScore.

        兼容:
        - 纯 JSON
        - ```json ... ``` 围栏
        - 含前后多余文字
        """
        text = llm_output.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1)
        else:
            json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
            if json_match:
                text = json_match.group(0)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return JudgeScore(
                score=0,
                reasoning=f"parse error: {llm_output[:100]}",
                raw_output=llm_output,
            )

        score_raw = data.get("score", 0)
        try:
            score = int(score_raw)
            score = max(0, min(5, score))
        except (TypeError, ValueError):
            score = 0

        return JudgeScore(
            score=score,
            reasoning=data.get("reasoning", ""),
            criteria=data.get("criteria", {}),
            raw_output=llm_output,
        )

    async def judge(
        self,
        query: str,
        prediction: str,
        reference: str,
    ) -> JudgeScore:
        """对单条预测评分."""
        prompt = self._build_prompt(query, prediction, reference)
        try:
            output = await self.llm_call_fn(prompt)
        except Exception as e:
            return JudgeScore(
                score=0,
                reasoning=f"LLM call failed: {type(e).__name__}: {e}",
            )
        return self._parse_output(output)

    async def judge_batch(
        self,
        items: list[dict],
    ) -> list[JudgeScore]:
        """批量评分."""
        import asyncio
        tasks = [
            self.judge(
                query=item["query"],
                prediction=item["prediction"],
                reference=item.get("reference", ""),
            )
            for item in items
        ]
        return await asyncio.gather(*tasks)
