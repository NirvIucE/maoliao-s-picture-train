"""
Agent 服务：图片分析 + 对话助手
"""

import base64
import json
from pyexpat import model
from typing import AsyncGenerator
import httpx
from fastapi import HTTPException, status
from src.config import PROVIDER_CONFIG, MODEL_REGISTRY

def _get_model_config(model_id: str) -> tuple[dict, dict]:
    """根据模型 ID 查找模型描述 + 厂商配置，找不到抛异常"""
    model = next((m for m in MODEL_REGISTRY if m["id"] == model_id), None)
    if model is None: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"不支持的模型: {model_id}，可用模型: {[m['id'] for m in MODEL_REGISTRY]}",
        )
    provider = PROVIDER_CONFIG.get(model["provider"])
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"模型 '{model_id}' 对应的厂商 '{model['provider']}' 未配置",
        )
    return model, provider


async def stream_llm(model_id: str, messages: list[dict],) -> AsyncGenerator[str, None]:
    """
    通用 LLM 流式调用（兼容 OpenAI 格式）
    - 查注册表找到厂商 + API Key
    - 发送 POST /v1/chat/completions
    - 逐块 yield SSE 格式的文本
    """
    _, provider = _get_model_config(model_id)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{provider['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 1024,
            },
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI 服务返回错误: {response.status_code} - {error_text.decode(errors='ignore')[:200]}",
                )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # 去掉 "data: " 前缀
                    if data == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield f"data: {json.dumps({'chunk': content}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        continue

async def analyze_image(image_path: str, image_mime: str, model_id: str) -> AsyncGenerator[str, None]:
    """分析图片：读取文件 → base64 → 送视觉模型 → 流式返回"""
    # 读取图片并编码为 base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    data_url = f"data:{image_mime};base64,{image_data}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请用中文描述这张图片的内容，包括主体、场景、颜色、构图。然后给出 3-5 个适合这张图片的标签词（用逗号分隔，以「标签:」开头）。格式如下:\n\n描述: ...\n标签: tag1, tag2, tag3",
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    async for chunk in stream_llm(model_id, messages):
        yield chunk

async def chat(
    messages: list[dict], model_id: str
) -> AsyncGenerator[str, None]:
    """多轮对话（不附加图片，纯文本）"""
    async for chunk in stream_llm(model_id, messages):
        yield chunk

def get_available_models(type_filter: str | None = None) -> list[dict]:
    """获取可用模型列表，可选按类型筛选（text/vision）"""
    if type_filter:
        return [m for m in MODEL_REGISTRY if m["type"] == type_filter]
    return list(MODEL_REGISTRY)