"""
Agent 路由
"""

from fastapi import APIRouter, Depends

#StreamingResponse 是 FastAPI 内置的流式响应。
# media_type="text/event-stream" 告诉浏览器"这是一个 SSE 流，不要一次性等结果，逐块渲染"。
from fastapi.responses import StreamingResponse

from src.routers.users import get_current_user
from src.models.user import User
from src.schemas.agent import AnalyzeImageRequest, ChatRequest, ModelInfo
from src.services import agent_service, image_service
from sqlalchemy.orm import Session
from src.database import get_db

router = APIRouter(prefix="/api/agent", tags=["AI助手"])

@router.get("/models", response_model=list[ModelInfo])
def list_models():
    """返回可用 AI 模型列表"""
    return agent_service.get_available_models()

@router.post("/analyze-image")
async def analyze_image(
    req: AnalyzeImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 分析图片（流式返回）"""
    image = image_service.get_image_detail(db, req.image_id, current_user)

    return StreamingResponse(
        agent_service.analyze_image(image.file_path, image.mime_type, req.model),
        media_type="text/event-stream",
    )

@router.post("/chat")
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """AI 对话（流式返回）"""
    return StreamingResponse(
        agent_service.chat(req.messages, req.model),
        media_type="text/event-stream",
    )