"""
agent 模块接口测试：模型列表 / 对话 / 图片分析（见计划 3.1 节）

状态码依据实际路由 + agent_service：
- /models 公开 200，返回模型列表
- /chat：成功 200（SSE 流），text 模型 + image_id 400，不存在图 404，无 token 401
- /analyze-image：成功 200（SSE 流），不存在图 404，无 token 401
- respx mock httpx，不烧 API 额度
- mock_models fixture 已移至 conftest.py 共享
"""

import json

import httpx
import pytest
import respx

from src.config import LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TEMPERATURE
from src.services import agent_service

# mock httpx 返回的 SSE 响应（OpenAI 格式 chunk + [DONE]）
SSE_RESPONSE = (
    'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"世界"}}]}\n\n'
    'data: [DONE]\n\n'
)


class TestModels:
    def test_list_models(self, client):
        """GET /models → 200 + list（公开，无需 auth）"""
        r = client.get("/api/agent/models")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestChat:
    @respx.mock
    def test_chat_text_success(self, client, auth_headers, mock_models):
        """文本对话（mock httpx SSE）→ 200 + 含 chunk"""
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 200
        assert "你好" in r.text
        assert "世界" in r.text

    @respx.mock
    def test_chat_with_vision_image(self, client, auth_headers, test_image, mock_models):
        """视觉模型 + image_id 对话（mock httpx）→ 200"""
        respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "describe this"}],
                "model": "vision-model",
                "image_id": test_image,
            },
        )
        assert r.status_code == 200
        assert "你好" in r.text

    def test_chat_text_model_rejects_image(self, client, auth_headers, test_image, mock_models):
        """text 模型 + image_id → 400（路由层拦截，非视觉模型拒绝带图）"""
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "text-model",
                "image_id": test_image,
            },
        )
        assert r.status_code == 400

    def test_chat_image_not_found(self, client, auth_headers, mock_models):
        """不存在的 image_id → 404"""
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "vision-model",
                "image_id": 9999,
            },
        )
        assert r.status_code == 404

    def test_chat_unauthorized(self, client):
        """无 token → 401"""
        r = client.post(
            "/api/agent/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 401


class TestAnalyzeImage:
    @respx.mock
    def test_analyze_image_success(self, client, auth_headers, test_image, mock_models):
        """图片分析（mock httpx SSE）→ 200 + 含 chunk"""
        respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        r = client.post(
            "/api/agent/analyze-image",
            headers=auth_headers,
            json={"image_id": test_image, "model": "vision-model"},
        )
        assert r.status_code == 200
        assert "你好" in r.text

    def test_analyze_image_not_found(self, client, auth_headers, mock_models):
        """不存在的 image_id → 404"""
        r = client.post(
            "/api/agent/analyze-image",
            headers=auth_headers,
            json={"image_id": 9999, "model": "vision-model"},
        )
        assert r.status_code == 404

    def test_analyze_image_unauthorized(self, client):
        """无 token → 401"""
        r = client.post(
            "/api/agent/analyze-image",
            json={"image_id": 1, "model": "vision-model"},
        )
        assert r.status_code == 401


class TestContextTrim:
    """阶段 14：滑动窗口上下文裁剪（纯函数）"""

    def test_short_history_unchanged(self):
        """未超限时消息原样保留"""
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
            {"role": "user", "content": "介绍一下图库功能"},
        ]
        out = agent_service._trim_context(msgs, max_tokens=4096)
        assert out == msgs

    def test_system_and_last_kept(self):
        """超限时：system 与最后一条提问保留，最旧消息被丢弃"""
        long_first = "第一轮：" + "内容" * 2000
        msgs = [
            {"role": "system", "content": "你是图库助手"},
            {"role": "user", "content": long_first},
            {"role": "assistant", "content": "好的"},
            {"role": "user", "content": "最后一轮提问"},
        ]
        out = agent_service._trim_context(msgs, max_tokens=100)
        assert out[0]["role"] == "system"  # system 永远保留
        assert out[-1]["content"] == "最后一轮提问"  # 最近提问保留
        assert all(m["content"] != long_first for m in out)  # 最旧消息被丢弃

    def test_estimates_total_within_limit(self):
        """裁剪后总 token 不超过上限"""
        msgs = [
            {"role": "user", "content": "A" * 100},
            {"role": "assistant", "content": "B" * 100},
            {"role": "user", "content": "C" * 100},
            {"role": "user", "content": "D" * 100},
        ]
        out = agent_service._trim_context(msgs, max_tokens=60)
        total = sum(agent_service._message_tokens(m) for m in out)
        assert total <= 60

    def test_multimodal_message_weight(self):
        """多模态消息（图片）按固定权重估算"""
        msgs = [{
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:xxx"}}],
        }]
        assert agent_service._message_tokens(msgs[0]) >= 512


class TestChatParams:
    """阶段 14：temperature/max_tokens 参数化透传"""

    @respx.mock
    def test_chat_custom_params(self, client, auth_headers, mock_models):
        """调用方覆盖 temperature/max_tokens → 请求体包含自定义值"""
        route = respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "text-model",
                "temperature": 0.1,
                "max_tokens": 64,
            },
        )
        assert r.status_code == 200
        body = json.loads(route.calls.last.request.content)
        assert body["temperature"] == 0.1
        assert body["max_tokens"] == 64

    @respx.mock
    def test_chat_default_params(self, client, auth_headers, mock_models):
        """未传时使用全局默认值"""
        route = respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        body = json.loads(route.calls.last.request.content)
        assert body["temperature"] == LLM_DEFAULT_TEMPERATURE
        assert body["max_tokens"] == LLM_DEFAULT_MAX_TOKENS

    @respx.mock
    def test_analyze_has_system_role(self, client, auth_headers, test_image, mock_models):
        """analyze_image 请求体 messages 含 system 角色与格式示例（prompt 工程）"""
        route = respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=SSE_RESPONSE)
        )
        r = client.post(
            "/api/agent/analyze-image",
            headers=auth_headers,
            json={"image_id": test_image, "model": "vision-model"},
        )
        assert r.status_code == 200
        body = json.loads(route.calls.last.request.content)
        assert body["messages"][0]["role"] == "system"
        assert "示例" in body["messages"][0]["content"]  # few-shot 格式示例存在


class TestToolCallParsing:
    """阶段 20：工具调用分片的解析（OpenAI 兼容协议里 tool_calls 是分片下发的）"""

    def test_merge_fragments_by_index(self):
        """id/name 在首片，arguments 分段到达 → 必须按 index 归位并拼接"""
        acc: dict = {}
        agent_service._merge_tool_call_delta(acc, [{
            "index": 0,
            "id": "call_a",
            "type": "function",
            "function": {"name": "search_images", "arguments": ""},
        }])
        agent_service._merge_tool_call_delta(
            acc, [{"index": 0, "function": {"arguments": '{"tag"'}}]
        )
        agent_service._merge_tool_call_delta(
            acc, [{"index": 0, "function": {"arguments": ': "猫猫"}'}}]
        )

        assert acc[0]["id"] == "call_a"
        assert acc[0]["function"]["name"] == "search_images"
        assert acc[0]["function"]["arguments"] == '{"tag": "猫猫"}'

    def test_merge_keeps_parallel_calls_separate(self):
        """同一条消息里多个工具调用：各占一个槽位，不能互相覆盖"""
        acc: dict = {}
        agent_service._merge_tool_call_delta(acc, [
            {"index": 0, "id": "c0", "function": {"name": "search_images", "arguments": "{}"}},
            {"index": 1, "id": "c1", "function": {"name": "get_image_info", "arguments": ""}},
        ])
        agent_service._merge_tool_call_delta(acc, [
            {"index": 1, "function": {"arguments": '{"image_id": 7}'}},
        ])

        assert sorted(acc) == [0, 1]
        assert acc[1]["function"]["name"] == "get_image_info"
        assert acc[1]["function"]["arguments"] == '{"image_id": 7}'

    def test_merge_tolerates_missing_fields(self):
        """厂商实现不统一：缺 index / 缺 function 也不能抛异常"""
        acc: dict = {}
        agent_service._merge_tool_call_delta(acc, [{"function": {"name": "search_images"}}])
        agent_service._merge_tool_call_delta(acc, [{}])

        assert acc[0]["function"]["name"] == "search_images"
        assert acc[0]["function"]["arguments"] == ""
