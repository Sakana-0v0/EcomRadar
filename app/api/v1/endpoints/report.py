"""Report API - 含 HITL 审批与断点续跑.

端点:
- POST /api/v1/report/generate - 启动报告生成
- POST /api/v1/report/{task_id}/resume - 审批后恢复
- GET /api/v1/report/{task_id}/status - 查询状态
"""
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.graph.state import GraphState
from app.graph.workflow import graph
from app.schemas.request import ReportRequest
from app.core.checkpointer import get_checkpointer
from app.services.governance.state_recovery import StateRecovery
from app.graph.workflow import PIPELINE_ORDER


router = APIRouter()


class ResumeRequest(BaseModel):
    """审批恢复请求."""
    approved: bool = Field(default=True, description="是否通过审批")
    override_state: dict = Field(default_factory=dict, description="状态覆盖 (可选)")


class StatusResponse(BaseModel):
    """任务状态响应."""
    task_id: str
    next_node: str | None
    is_complete: bool
    history_count: int


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """Generate report with SSE streaming.

    注意: 当工作流配置 interrupt_before=["publisher"] 时,
    流程在 Publisher 节点前暂停, 返回的 SSE 事件含 'paused' 状态.
    客户端需调用 POST /{task_id}/resume 继续.
    """
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    async def event_stream():
        config = {"configurable": {"thread_id": task_id}}
        initial_state: GraphState = {
            "task_id": task_id,
            "urls": request.urls,
            "scraped_content": {},
            "chunks": [],
            "context_docs": [],
            "report": "",
            "quality_score": 0,
            "retry_count": 0,
            "is_degraded": False,
            "error_messages": [],
        }

        try:
            async for event in graph.astream(initial_state, config=config):
                for node_name, node_data in event.items():
                    if "__interrupt__" in node_data:
                        yield {
                            "event": "paused",
                            "data": f"task_id={task_id}; node=awaiting_human_approval",
                        }
                        continue
                    if "report" in node_data and node_data["report"]:
                        yield {"event": "report", "data": node_data["report"]}
                    if "quality_score" in node_data:
                        score = node_data.get("quality_score", 0)
                        yield {"event": "score", "data": str(score)}
                    if "published_channels" in node_data:
                        yield {
                            "event": "published",
                            "data": ",".join(node_data["published_channels"] or []),
                        }
        except Exception as e:
            yield {"event": "error", "data": str(e)}
            return

        yield {"event": "done", "data": task_id}

    return EventSourceResponse(event_stream())


@router.post("/{task_id}/resume")
async def resume_report(task_id: str, request: ResumeRequest):
    """审批后恢复工作流.

    工作流会在 Publisher 节点前中断,
    客户端审批后调用此接口恢复.

    approved=False 时, 跳过 Publisher, 流程结束.
    """
    if not request.approved:
        return {
            "task_id": task_id,
            "status": "rejected",
            "message": "report rejected, skipped publisher",
        }

    config = {"configurable": {"thread_id": task_id}}

    try:
        updated_state: dict = {}
        async for event in graph.astream(None, config=config):
            for node_name, node_data in event.items():
                if "__interrupt__" in node_data:
                    continue
                if "published_channels" in node_data:
                    updated_state["published_channels"] = node_data["published_channels"]
                if "report" in node_data:
                    updated_state["report"] = node_data["report"]

        return {
            "task_id": task_id,
            "status": "resumed",
            "published_channels": updated_state.get("published_channels", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/status", response_model=StatusResponse)
async def get_status(task_id: str):
    """查询任务状态.

    内部使用 StateRecovery 检查最近 checkpoint.
    """
    store = get_checkpointer(backend="memory")
    recovery = StateRecovery(store)
    plan = await recovery.build_plan(task_id, pipeline_order=PIPELINE_ORDER)

    if plan is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")

    return StatusResponse(
        task_id=task_id,
        next_node=plan.next_node,
        is_complete=plan.is_complete,
        history_count=plan.metadata.get("checkpoint_count", 0),
    )
