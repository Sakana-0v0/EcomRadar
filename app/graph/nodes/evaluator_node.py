from app.graph.state import GraphState
from app.services.evaluator import evaluate_report
from app.core.logging import get_logger

logger = get_logger(__name__)


def evaluator_node(state: GraphState) -> GraphState:
    """Evaluate the generated report quality."""
    report = state.get("report", "")
    try:
        score = evaluate_report(report)
        logger.info(
            "evaluator scored",
            extra={"node": "evaluator", "quality_score": score, "report_len": len(report)},
        )
        return {"quality_score": score}
    except Exception as e:
        logger.error(
            "evaluator failed",
            extra={"node": "evaluator", "error": str(e)},
        )
        return {"quality_score": 0}