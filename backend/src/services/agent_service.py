"""
Agent 服务：图片分析 + 对话助手
"""

import base64
import json
from collections.abc import AsyncGenerator

import httpx
from fastapi import HTTPException, status

from src.config import (
    CHAT_MAX_CONTEXT_TOKENS,
    LLM_DEFAULT_MAX_TOKENS,
    LLM_DEFAULT_TEMPERATURE,
    MODEL_REGISTRY,
    PROVIDER_CONFIG,
)


def _encode_image(image_path: str) -> str:
    """读取本地图片文件并编码为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

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


def _estimate_tokens(text: str) -> int:
    """粗略估算文本 token 数：中文字符≈1.5 token、其余≈4 字符/token（不依赖 tiktoken，够用即可）"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk * 1.5 + other / 4)


def _message_tokens(message: dict) -> int:
    """估算单条消息 token 数（兼容纯文本与多模态 content）"""
    content = message.get("content", "")
    if isinstance(content, str):
        return _estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict):
                text = part.get("text", "")
                if text:
                    total += _estimate_tokens(str(text))
                elif part.get("type") == "image_url":
                    total += 512  # 图片按固定权重估算（一张图等效 token）
        return total
    return _estimate_tokens(str(content))


def _trim_context(messages: list[dict], max_tokens: int) -> list[dict]:
    """
    滑动窗口裁剪对话上下文：
    - system 消息永远保留（不参与裁剪）
    - 最后一条消息（当前提问）永远保留
    - 从最旧的普通消息开始丢弃，直到总 token ≤ 上限
    """
    if not messages:
        return messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    others = [m for m in messages if m.get("role") != "system"]
    if not others:
        return messages
    last = others[-1]
    history = others[:-1]
    while history and (
        sum(_message_tokens(m) for m in system_msgs)
        + sum(_message_tokens(m) for m in history)
        + _message_tokens(last)
        > max_tokens
    ):
        history.pop(0)  # 丢弃最旧的
    return system_msgs + history + [last]


async def stream_llm(
    model_id: str,
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """
    通用 LLM 流式调用（兼容 OpenAI 格式）
    - 查注册表找到厂商 + API Key
    - 发送 POST /v1/chat/completions
    - 逐块 yield SSE 格式的文本
    - temperature/max_tokens 未传时使用全局默认值，调用方可按任务覆盖
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
                "temperature": LLM_DEFAULT_TEMPERATURE if temperature is None else temperature,
                "max_tokens": LLM_DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens,
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

async def complete_llm(model_id: str, messages: list[dict]) -> str:
    """非流式调用：复用 stream_llm 把流收集为完整文本返回（用于 AI 搜索等需要完整结果的场景）"""
    collected: list[str] = []
    async for chunk in stream_llm(model_id, messages):
        if chunk.startswith("data: "):
            try:
                payload = json.loads(chunk[6:])
                text = payload.get("chunk", "")
                if text:
                    collected.append(text)
            except json.JSONDecodeError:
                continue
    return "".join(collected)


async def analyze_image(
    image_path: str,
    image_mime: str,
    model_id: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """分析图片：读取文件 → base64 → 送视觉模型 → 流式返回（system 角色 + 格式示例约束输出）"""
    # 读取图片并编码为 base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    data_url = f"data:{image_mime};base64,{image_data}"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的图片分析助手。请用中文描述图片的主体、场景、颜色与构图，"
                "并给出 3-5 个贴切标签。必须严格按以下格式输出，不要添加其他内容：\n\n"
                "示例：\n"
                "描述: 画面主体是一只橘猫，趴在窗台上，暖色侧光，构图居中\n"
                "标签: 猫, 橘色, 窗台, 宠物"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "请分析这张图片："},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    async for chunk in stream_llm(model_id, messages, temperature, max_tokens):
        yield chunk

async def chat(
    messages: list[dict],
    model_id: str,
    image=None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """多轮对话，支持附带图片进行视觉分析（入口先做滑动窗口裁剪，防止上下文超限）"""
    messages = _trim_context(messages, CHAT_MAX_CONTEXT_TOKENS)
    if image is not None:
        # 读取图片文件 → base64
        img_base64 = _encode_image(image.file_path)
        img_url = f"data:{image.mime_type};base64,{img_base64}"
        # 在当前 messages 最后追加一个多模态 user message
        messages = messages + [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": "请结合这张图片回答用户的问题。"},
            ]
        }]

    async for chunk in stream_llm(model_id, messages, temperature, max_tokens):
        yield chunk

def get_available_models(type_filter: str | None = None) -> list[dict]:
    """获取可用模型列表，可选按类型筛选（text/vision）"""
    if type_filter:
        return [m for m in MODEL_REGISTRY if m["type"] == type_filter]
    return list(MODEL_REGISTRY)
