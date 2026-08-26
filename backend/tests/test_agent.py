"""agent 模块接口测试：模型列表 / 对话 / 图片分析（见计划 3.1 节）

状态码依据实际路由 + agent_service：
- /models 公开 200，返回模型列表
- /chat：成功 200（SSE 流），text 模型 + image_id 400，不存在图 404，无 token 401
- /analyze-image：成功 200（SSE 流），不存在图 404，无 token 401
- respx mock httpx，不烧 API 额度
"""

import httpx
import pytest
import respx

from src.services import agent_service

# mock httpx 返回的 SSE 响应（OpenAI 格式 chunk + [DONE]）
SSE_RESPONSE = (
    'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"世界"}}]}\n\n'
    'data: [DONE]\n\n'
)


@pytest.fixture
def mock_models(monkeypatch):
    """注入 mock 模型注册表 + 厂商配置（避免依赖 .env 的 AI_MODELS）"""
    fake_registry = [
        {"id": "text-model", "name": "文本模型", "type": "text", "provider": "deepseek"},
        {"id": "vision-model", "name": "视觉模型", "type": "vision", "provider": "siliconflow"},
    ]
    fake_providers = {
        "deepseek": {"api_key": "fake-key", "base_url": "https://api.deepseek.com/v1"},
        "siliconflow": {"api_key": "fake-key", "base_url": "https://api.siliconflow.cn/v1"},
    }
    from src.routers import agent as agent_router

    monkeypatch.setattr(agent_router, "MODEL_REGISTRY", fake_registry)
    monkeypatch.setattr(agent_service, "MODEL_REGISTRY", fake_registry)
    monkeypatch.setattr(agent_service, "PROVIDER_CONFIG", fake_providers)
    return fake_registry


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
