import re


def evaluate_report(report: str) -> int:
    """Evaluate report quality across three dimensions.

    Scoring:
    - Factuality (40%): Has summary section with key points
    - Structure (30%): Has markdown headers (##)
    - Coherence (30%): Has substantial content (>100 chars)

    Returns:
        Quality score 0-100
    """
    if not report:
        return 0

    score = 0

    has_summary = bool(re.search(r'摘要|总结|核心|要点', report))
    has_structure = bool(re.search(r'##\s+\w+', report))
    has_content = len(report) > 100

    score += 40 if has_summary else 20
    score += 30 if has_structure else 15
    score += 30 if has_content else 10

    return min(100, max(0, score))