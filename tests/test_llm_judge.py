"""LLM Judge 单元测试.

LLM-as-Judge 模式:
- 用更强的 LLM 给生成结果打分 (1-5)
- 适合开放式问答 / 摘要类任务
- 与传统 EM/F1 互补
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.eval.llm_judge import LLMJudge, JudgeScore


class TestJudgeScore:
    def test_to_dict(self):
        s = JudgeScore(
            score=4,
            reasoning="回答基本正确, 但缺少 SKU 细节",
            criteria={"correctness": 0.8, "completeness": 0.6},
        )
        d = s.to_dict()
        assert d["score"] == 4
        assert "reasoning" in d
        assert d["criteria"]["correctness"] == 0.8


class TestLLMJudge:
    @pytest.mark.asyncio
    async def test_parse_valid_json_score(self):
        judge = LLMJudge()
        llm_output = '{"score": 4, "reasoning": "基本正确", "criteria": {"accuracy": 0.85}}'
        score = judge._parse_output(llm_output)
        assert score.score == 4
        assert score.reasoning == "基本正确"

    @pytest.mark.asyncio
    async def test_parse_with_markdown_fences(self):
        judge = LLMJudge()
        llm_output = '```json\n{"score": 5, "reasoning": "完美", "criteria": {}}\n```'
        score = judge._parse_output(llm_output)
        assert score.score == 5

    @pytest.mark.asyncio
    async def test_parse_invalid_returns_default(self):
        judge = LLMJudge()
        score = judge._parse_output("not valid json")
        assert score.score == 0
        assert "parse error" in score.reasoning.lower()

    @pytest.mark.asyncio
    async def test_judge_invokes_llm(self):
        judge = LLMJudge()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"score": 4, "reasoning": "good", "criteria": {}}'}}]
        }
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            result = await judge.judge(
                query="小度价格",
                prediction="329元",
                reference="329元",
            )
            assert isinstance(result, JudgeScore)
            assert result.score == 4

    @pytest.mark.asyncio
    async def test_judge_batch(self):
        judge = LLMJudge()
        items = [
            {"query": "q1", "prediction": "p1", "reference": "r1"},
            {"query": "q2", "prediction": "p2", "reference": "r2"},
        ]
        with patch.object(judge, "judge", new=AsyncMock(return_value=JudgeScore(score=4, reasoning="x", criteria={}))):
            results = await judge.judge_batch(items)
            assert len(results) == 2
            assert all(r.score == 4 for r in results)
