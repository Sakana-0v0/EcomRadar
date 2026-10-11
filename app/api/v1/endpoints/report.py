from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from app.graph.state import GraphState
from app.graph.workflow import graph
from app.schemas.request import ReportRequest

router = APIRouter()


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """Generate research report with SSE streaming."""

    async def event_stream():
        initial_state: GraphState = {
            "urls": request.urls,
            "scraped_content": {},
            "chunks": [],
            "context_docs": [],
            "report": "",
            "quality_score": 0,
            "retry_count": 0,
            "is_degraded": False,
            "error_messages": []
        }

        async for event in graph.astream(initial_state):
            for node_name, node_data in event.items():
                if "report" in node_data and node_data["report"]:
                    yield {"event": "report", "data": node_data["report"]}
            if "quality_score" in str(event):
                for node_name, node_data in event.items():
                    if "quality_score" in node_data:
                        score = node_data.get("quality_score", 0)
                        yield {"event": "score", "data": str(score)}

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())
