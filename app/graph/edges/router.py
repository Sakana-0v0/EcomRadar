"""Router 条件边路由."""
from app.graph.state import GraphState


def should_retry(state: GraphState) -> str:
    """Evaluator 之后的路由.

    Returns:
        "rewrite"  - 质量 < 75 且重试 < 2 次, 回到 Writer
        "publish"  - 质量 >= 75, 进入 Publisher
        "end"      - 重试 >= 2 次, 强制收敛
    """
    quality = state.get("quality_score", 0)
    retry = state.get("retry_count", 0)
    if quality >= 75:
        return "publish"
    if retry >= 2:
        return "end"
    return "rewrite"


def should_publish(state: GraphState) -> str:
    """(预留) Publisher 后的路由.

    当前 pipeline 是线性, Publisher 后即 END, 此函数预留扩展.
    """
    return "end"
