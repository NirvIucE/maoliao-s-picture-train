"""
Agent 服务：图片分析 + 对话助手
"""

import base64
import json
from collections.abc import AsyncGenerator

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.config import (
    AGENT_MAX_TOOL_STEPS,
    CHAT_MAX_CONTEXT_TOKENS,
    LLM_DEFAULT_MAX_TOKENS,
    LLM_DEFAULT_TEMPERATURE,
    MODEL_REGISTRY,
    PROVIDER_CONFIG,
)
from src.models.user import User
from src.services.agent_tools import TOOL_SCHEMAS, execute_tool


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


def _merge_tool_call_delta(acc: dict[int, dict], fragments: list[dict]) -> None:
    """把流式 tool_calls 增量合并进累积表（阶段 20）

    OpenAI 兼容协议里工具调用是**分片**下发的：同一个调用的 id / name 出现在首个分片，
    `arguments` 则被切成若干段陆续到达，靠 `index` 归位。因此这里按 index 建槽并做字符串拼接，
    不能简单的「后到的覆盖先到的」。
    """
    for frag in fragments:
        index = frag.get("index", 0)
        slot = acc.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if frag.get("id"):
            slot["id"] = frag["id"]
        func = frag.get("function") or {}
        if func.get("name"):
            slot["function"]["name"] += func["name"]
        if func.get("arguments"):
            slot["function"]["arguments"] += func["arguments"]


async def iter_llm_stream(
    model_id: str,
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    底层流式调用：查注册表 → POST /v1/chat/completions → 产出**规范化事件**

    - `{"type": "text", "content": str}`：正文增量
    - `{"type": "tool_calls", "tool_calls": [...]}`：模型请求调用工具（流结束后一次性给出）

    与 `stream_llm` 的分工：本函数不假设调用方只要文本，所以返回结构化事件；
    `stream_llm` 是它的「只要正文」封装，保持既有 SSE 契约不变。
    """
    _, provider = _get_model_config(model_id)

    payload = {
        "model": model_id,
        "messages": messages,
        "stream": True,
        "temperature": LLM_DEFAULT_TEMPERATURE if temperature is None else temperature,
        "max_tokens": LLM_DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{provider['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI 服务返回错误: {response.status_code} - {error_text.decode(errors='ignore')[:200]}",
                )

            acc: dict[int, dict] = {}
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]  # 去掉 "data: " 前缀
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                # choices 可能为空列表，故用 `or [{}]` 而非 `get(..., [{}])`
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield {"type": "text", "content": content}
                fragments = delta.get("tool_calls")
                if fragments:
                    _merge_tool_call_delta(acc, fragments)

            if acc:
                yield {"type": "tool_calls", "tool_calls": [acc[i] for i in sorted(acc)]}


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

    阶段 20：改为 `iter_llm_stream` 的文本封装（工具调用事件在此被丢弃），
    输出契约与改造前一致——仍为 `data: {"chunk": ...}` 若干行 + 结尾 `data: [DONE]`。
    """
    async for event in iter_llm_stream(model_id, messages, temperature, max_tokens):
        if event["type"] == "text":
            yield f"data: {json.dumps({'chunk': event['content']}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"

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


# ── 阶段 20：工具调用循环 ──

AGENT_SYSTEM_PROMPT = """你是「猫里奥云图库」的 AI 助手，帮用户管理他自己的个人图库。

你可以调用以下工具（只有用户的**个人图库**可操作）：
- search_images：按标签或名称检索用户的个人图库
- get_image_info：查看某张图片的详情，以及它在公共图库的提交状态
- submit_to_public：准备「提交到公共图库」。它不会真正提交，需要用户在界面上点确认后才会生效

行为规则：
1. 用户提到某张具体图片时，先用工具确认，不要凭空猜测图片 id。
2. 检索不到或候选过多时，如实告知并列出来，请用户补充信息，不要硬猜。
3. 用户表达「提交到公共图库」的意图时，调用 submit_to_public，然后提醒用户在确认卡片上点击确认。
4. 工具结果里的 error 字段说明了失败原因，请据此向用户解释，不要用完全相同的参数重复调用。
5. 用简洁的中文回答，不要输出 JSON、工具名等内部细节。"""


def model_supports_tools(model_id: str) -> bool:
    """该模型是否被标记支持 function calling（未标记视为不支持）"""
    model = next((m for m in MODEL_REGISTRY if m["id"] == model_id), None)
    return bool(model and model.get("tools"))


def _sse(payload: dict) -> str:
    """把事件序列化为 SSE 行（与既有 `{"chunk": ...}` 契约并存）"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _tool_args_preview(raw_arguments: str) -> object:
    """给前端展示的工具参数：能解析成 JSON 就给对象，否则原样回字符串"""
    try:
        return json.loads(raw_arguments) if raw_arguments.strip() else {}
    except json.JSONDecodeError:
        return raw_arguments


async def run_tool_loop(
    messages: list[dict],
    model_id: str,
    db: Session,
    user: User,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """带工具调用的对话循环（阶段 20）

    在**单次 HTTP 请求内**闭环：模型要工具 → 本地执行 → 结果回灌 → 继续生成，
    前端只看到 SSE 事件与最终文本，不需要理解 OpenAI 的 tool 消息协议。

    上下文只在入口裁剪一次：循环中途裁剪可能丢掉 `assistant(tool_calls)`
    却留下配对的 `role=tool` 消息，上游会直接报错。
    """
    if not any(m.get("role") == "system" for m in messages):
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}] + messages
    messages = _trim_context(messages, CHAT_MAX_CONTEXT_TOKENS)

    cache: dict[str, dict] = {}  # 单轮内相同工具+相同参数只执行一次

    for _ in range(AGENT_MAX_TOOL_STEPS):
        tool_calls: list[dict] = []
        async for event in iter_llm_stream(
            model_id, messages, temperature, max_tokens, TOOL_SCHEMAS
        ):
            if event["type"] == "text":
                yield _sse({"chunk": event["content"]})
            else:
                tool_calls = event["tool_calls"]

        if not tool_calls:
            break

        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        for call in tool_calls:
            func = call.get("function") or {}
            name = func.get("name", "")
            raw_arguments = func.get("arguments") or ""
            preview = _tool_args_preview(raw_arguments)
            yield _sse({"type": "tool_call", "name": name, "args": preview})

            key = f"{name}:{raw_arguments}"
            result = cache.get(key)
            if result is None:
                result = execute_tool(name, raw_arguments, db, user)
                cache[key] = result

            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or "",
                "content": json.dumps(result, ensure_ascii=False),
            })

            if result.get("requires_confirmation"):
                # 写操作不在这里执行：只把待确认参数交给前端，由用户点确认后走既有 REST 端点
                yield _sse({"type": "confirm", "action": name, "payload": result.get("data") or {}})
            yield _sse({
                "type": "tool_result",
                "name": name,
                "ok": bool(result.get("ok")),
                "summary": result.get("summary", ""),
                "data": result.get("data"),
            })
    else:
        # 步数用尽仍未收敛：去掉工具再问一次，强制模型基于已有信息作答
        async for event in iter_llm_stream(model_id, messages, temperature, max_tokens):
            if event["type"] == "text":
                yield _sse({"chunk": event["content"]})

    yield "data: [DONE]\n\n"


def get_available_models(type_filter: str | None = None) -> list[dict]:
    """获取可用模型列表，可选按类型筛选（text/vision）"""
    if type_filter:
        return [m for m in MODEL_REGISTRY if m["type"] == type_filter]
    return list(MODEL_REGISTRY)
