from app.graph.state import GraphState
from app.services.evaluator import evaluate_report


def evaluator_node(state: GraphState) -> GraphState:
    """Evaluate the generated report quality."""
    report = state.get("report", "")
    score = evaluate_report(report)
    return {"quality_score": score}