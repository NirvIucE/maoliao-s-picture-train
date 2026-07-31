
"""
Agent Schema
"""
from pydantic import BaseModel

class AnalyzeImageRequest(BaseModel):
    """图片分析请求"""
    image_id: int
    model: str = "Qwen/Qwen3-VL-32B-Instruct" # 默认用视觉模型

class ChatRequest(BaseModel):
    """对话请求"""
    messages:list[dict] # [{"role": "user", "content": "..."}]
    model: str = "deepseek-chat" # 默认用文本模型
    
class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    type: str  # "text" 或 "vision"