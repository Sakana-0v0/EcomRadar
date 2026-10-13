from app.graph.state import GraphState
from app.services.evaluator import evaluate_competitor_report
from app.core.logging import get_logger

logger = get_logger(__name__)


async def evaluator_node(state: GraphState) -> GraphState:
    """Evaluate the generated report quality using 5-dimension scoring."""
    report = state.get("report", "")
    try:
        result = evaluate_competitor_report(report)
        logger.info(
            "evaluator scored",
            extra={
                "node": "evaluator",
                "quality_score": result.score,
                "passed": result.passed,
                "dimensions": result.dimensions,
                "missing": result.missing_sections,
            },
        )
        return {
            "quality_score": result.score,
        }
    except Exception as e:
        logger.error(
            "evaluator failed",
            extra={"node": "evaluator", "error": str(e)},
        )
        return {"quality_score": 0, "is_degraded": True}
