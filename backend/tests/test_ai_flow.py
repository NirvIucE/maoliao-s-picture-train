"""AI 应用测试：SSE 解析健壮性 / AI 错误降级 / payload 构造 / 真实冒烟（见计划第 5 节）

与 test_agent.py 的区别：
- test_agent.py：验证 API 契约（状态码、权限、响应格式）—— happy path + 基本错误
- test_ai_flow.py：验证 AI 专项问题—— SSE 畸形 chunk / AI 返回错误 / base64 payload 格式

覆盖 agent_service.py 未覆盖行：
- L62-67：AI 返回非 200 → raise HTTPException(502)
- L81-82：json.JSONDecodeError → continue（畸形 chunk 不崩）
"""

import json
import os

import httpx
import pytest
import respx
from fastapi import HTTPException

from src.services import agent_service

# 标准 SSE 响应（供 payload 验证测试使用）
SSE_RESPONSE = (
    'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n'
    'data: [DONE]\n\n'
)


class TestSSEParsing:
    """SSE 流式解析健壮性：畸形/空/多余 chunk 不崩"""

    @respx.mock
    def test_malformed_json_skipped(self, client, auth_headers, mock_models):
        """畸形 JSON chunk 被跳过，有效 chunk 仍正常返回（L81-82）"""
        malformed_sse = (
            'data: {invalid json}\n\n'
            'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n'
            'data: [DONE]\n\n'
        )
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=malformed_sse)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 200
        assert "OK" in r.text  # 畸形 chunk 被跳过，有效 chunk 正常返回

    @respx.mock
    def test_empty_data_line_skipped(self, client, auth_headers, mock_models):
        """空 data 行被跳过（json.loads('') → JSONDecodeError → continue，L81-82）"""
        empty_data_sse = (
            "data: \n\n"
            'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n'
            'data: [DONE]\n\n'
        )
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=empty_data_sse)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 200
        assert "OK" in r.text

    @respx.mock
    def test_done_then_extra_chunk(self, client, auth_headers, mock_models):
        """[DONE] 后多余 chunk 不被处理（break 跳出循环，L72-74）"""
        done_extra_sse = (
            'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n'
            'data: [DONE]\n\n'
            'data: {"choices":[{"delta":{"content":"AFTER"}}]}\n\n'
        )
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=done_extra_sse)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 200
        assert "OK" in r.text
        assert "AFTER" not in r.text  # [DONE] 后的 chunk 不被处理


class TestAIErrors:
    """AI 返回非 200 → raise HTTPException(502)（L62-67）

    直接测试 stream_llm 生成器，避免 StreamingResponse 状态码已发送的复杂性。
    """

    @respx.mock
    async def test_ai_returns_401(self, mock_models):
        """AI 返回 401（API key 无效）→ 502"""
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(401, text='{"error":"invalid api key"}')
        )
        with pytest.raises(HTTPException) as exc_info:
            async for _ in agent_service.stream_llm(
                "text-model", [{"role": "user", "content": "hi"}]
            ):
                pass
        assert exc_info.value.status_code == 502

    @respx.mock
    async def test_ai_returns_429(self, mock_models):
        """AI 返回 429（限流）→ 502"""
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(429, text='{"error":"rate limit exceeded"}')
        )
        with pytest.raises(HTTPException) as exc_info:
            async for _ in agent_service.stream_llm(
                "text-model", [{"role": "user", "content": "hi"}]
            ):
                pass
        assert exc_info.value.status_code == 502

    @respx.mock
    async def test_ai_returns_500(self, mock_models):
        """AI 返回 500（服务异常）→ 502"""
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text='{"error":"internal server error"}')
        )
        with pytest.raises(HTTPException) as exc_info:
            async for _ in agent_service.stream_llm(
                "text-model", [{"role": "user", "content": "hi"}]
            ):
                pass
        assert exc_info.value.status_code == 502


class TestPayloadValidation:
    """多模态 payload 格式验证：抓取 httpx 请求，验证 base64 编码正确"""

    @respx.mock
    def test_chat_vision_payload_format(self, client, auth_headers, test_image, mock_models):
        """chat 带 image_id → 请求 payload 含 image_url + data:image/...;base64,...（L116-121）"""
        captured = {}

        def _capture(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, text=SSE_RESPONSE)

        respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(side_effect=_capture)
        client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "describe this"}],
                "model": "vision-model",
                "image_id": test_image,
            },
        )
        # 验证 payload 中最后一条消息是多模态格式
        last_msg = captured["body"]["messages"][-1]
        assert last_msg["role"] == "user"
        content = last_msg["content"]
        assert isinstance(content, list), "多模态消息 content 应为 list"
        # 找到 image_url 部分
        img_part = next((c for c in content if c.get("type") == "image_url"), None)
        assert img_part is not None, "payload 应包含 image_url 类型"
        assert img_part["image_url"]["url"].startswith("data:image/"), "URL 应以 data:image/ 开头"
        assert "base64," in img_part["image_url"]["url"], "URL 应包含 base64 编码"

    @respx.mock
    def test_analyze_image_payload_format(self, client, auth_headers, test_image, mock_models):
        """analyze-image → 请求 payload 含 base64 图片编码（L87-90）"""
        captured = {}

        def _capture(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, text=SSE_RESPONSE)

        respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(side_effect=_capture)
        client.post(
            "/api/agent/analyze-image",
            headers=auth_headers,
            json={"image_id": test_image, "model": "vision-model"},
        )
        # 验证 payload 包含 base64 图片
        last_msg = captured["body"]["messages"][-1]
        content = last_msg["content"]
        assert isinstance(content, list), "分析请求 content 应为多模态 list"
        img_part = next((c for c in content if c.get("type") == "image_url"), None)
        assert img_part is not None
        url = img_part["image_url"]["url"]
        assert url.startswith("data:image/png;base64,"), "应为 PNG base64 data URL"


class TestRealSmoke:
    """真实 AI 冒烟测试：验证 SSE 流式链路端到端通（需 .env API key）"""

    async def test_real_deepseek_chat(self):
        """真实调用 DeepSeek 文本对话，验证 SSE 流式响应；无 key 自动 skip"""
        from src.config import MODEL_REGISTRY, PROVIDER_CONFIG

        deepseek = PROVIDER_CONFIG.get("deepseek", {})
        if not deepseek.get("api_key"):
            pytest.skip("DeepSeek API key 未配置，跳过真实冒烟测试")

        # 找一个 DeepSeek 的 text 模型
        model = next(
            (m for m in MODEL_REGISTRY if m.get("provider") == "deepseek" and m.get("type") == "text"),
            None,
        )
        if not model:
            pytest.skip("MODEL_REGISTRY 中无 DeepSeek text 模型，跳过")

        # 真实调用，验证收到 SSE 数据
        chunks = []
        async for chunk in agent_service.stream_llm(
            model["id"], [{"role": "user", "content": "回复'OK'两个字"}]
        ):
            chunks.append(chunk)

        assert len(chunks) > 0, "应收到至少一个 SSE chunk"
        assert any("data:" in c for c in chunks), "chunk 应为 SSE 格式（data: ...）"
