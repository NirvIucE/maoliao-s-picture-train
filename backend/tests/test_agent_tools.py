"""
AI 助手工具调用测试（阶段 20）

分三层：

1. 工具单测：直接调 `execute_tool`，验证检索 / 详情 / 提交准备的行为与越权保护
2. 循环集成：respx 多段 mock，验证「模型要工具 → 本地执行 → 结果回灌 → 继续生成」闭环
3. 降级路径：未标记 tools 的模型请求体里不带 tools 字段（行为与改造前一致）

写操作的关键断言是**不写库**：`submit_to_public` 只校验并回传待确认参数，
真正的写动作由前端确认卡片触发既有 REST 端点，所以这里要盯住 public_images 计数不变。
"""

import json
from io import BytesIO

import httpx
import pytest
import respx
from PIL import Image as PILImage

from src.config import AGENT_MAX_TOOL_STEPS
from src.models.public_image import PublicImage
from src.models.user import User
from src.services import agent_service
from src.services.agent_tools import TOOL_NAMES, execute_tool

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


# ── SSE 构造与解析辅助 ──

def _chunk(delta: dict, finish_reason: str | None = None) -> str:
    """构造一条 OpenAI 兼容的流式分片"""
    payload = {"choices": [{"delta": delta, "finish_reason": finish_reason}]}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _text_frames(text: str) -> str:
    """普通文本回复（含结尾 [DONE]）"""
    return _chunk({"content": text}, "stop") + "data: [DONE]\n\n"


def _tool_call_frames(calls: list[dict]) -> str:
    """工具调用回复——**分片下发**，贴近真实协议

    真实流里同一个调用的 `id` / `name` 出现在首片，`arguments` 被切成若干段陆续到达，
    靠 `index` 归位。这里刻意也把 arguments 切成两段，顺带验证拼接逻辑（不能覆盖）。
    """
    frames = _chunk({"content": ""}, "tool_calls")  # 真实流里常有的空 content 前导片
    for index, call in enumerate(calls):
        args = call["arguments"]
        mid = len(args) // 2
        frames += _chunk({"tool_calls": [{
            "index": index,
            "id": call["id"],
            "type": "function",
            "function": {"name": call["name"], "arguments": args[:mid]},
        }]})
        frames += _chunk({"tool_calls": [{"index": index, "function": {"arguments": args[mid:]}}]})
    return frames + "data: [DONE]\n\n"


def _parse_sse(text: str) -> list[dict]:
    """把 SSE 响应体解析成事件列表（跳过 [DONE]）"""
    events = []
    for line in text.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            events.append(json.loads(line[6:]))
    return events


def _of_type(events: list[dict], type_: str) -> list[dict]:
    return [e for e in events if e.get("type") == type_]


def _chunks_of(events: list[dict]) -> list[str]:
    return [e["chunk"] for e in events if "chunk" in e]


# ── 数据准备辅助 ──

def _upload(client, headers, name: str) -> int:
    """上传一张 PNG 并指定 custom_name，返回 image_id"""
    buf = BytesIO()
    PILImage.new("RGB", (10, 10), (255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/images/upload",
        headers=headers,
        files={"file": (f"{name}.png", buf, "image/png")},
        data={"custom_name": name},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_tags(client, headers, image_id: int, tags: list[str]) -> None:
    """给个人图库图片打标签"""
    r = client.post(f"/api/images/{image_id}/tags", headers=headers, json={"tags": tags})
    assert r.status_code == 200, r.text


def _submit(client, headers, image_id: int, tags: list[str] | None = None) -> int:
    """走既有 REST 端点真正提交公共图库，返回 public_id"""
    payload: dict = {"image_id": image_id}
    if tags:
        payload["tags"] = tags
    r = client.post("/api/public/images", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _user(db_session, username: str = "alice") -> User:
    user = db_session.query(User).filter_by(username=username).first()
    assert user is not None, f"用户 {username} 不存在"
    return user


def _call(db_session, user: User, name: str, args: dict) -> dict:
    """以模型的身份调用工具（参数走 JSON 字符串，和真实回灌一致）"""
    return execute_tool(name, json.dumps(args, ensure_ascii=False), db_session, user)


@pytest.fixture
def bob(client):
    """第二个用户：越权保护用例需要「别人的图」"""
    payload = {"username": "bob", "email": "bob@test.com", "password": "pass1234"}
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": "bob", "password": "pass1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestSearchImages:
    """search_images：按标签（精确）/ 名称（模糊）检索个人图库"""

    def test_by_tag(self, client, auth_headers, db_session):
        img = _upload(client, auth_headers, "抓到的老鼠")
        _add_tags(client, auth_headers, img, ["猫猫"])
        result = _call(db_session, _user(db_session), "search_images", {"tag": "猫猫"})
        assert result["ok"] is True
        assert [item["id"] for item in result["data"]] == [img]
        assert result["data"][0]["tags"] == ["猫猫"]
        assert "找到 1 张" in result["summary"]

    def test_tag_accepts_hash_prefix(self, client, auth_headers, db_session):
        """模型可能带上 # 前缀，工具侧要能容错"""
        img = _upload(client, auth_headers, "晒太阳")
        _add_tags(client, auth_headers, img, ["猫猫"])
        result = _call(db_session, _user(db_session), "search_images", {"tag": "#猫猫"})
        assert [item["id"] for item in result["data"]] == [img]

    def test_by_keyword(self, client, auth_headers, db_session):
        img = _upload(client, auth_headers, "麦当劳门口的橘猫")
        result = _call(db_session, _user(db_session), "search_images", {"keyword": "麦当劳"})
        assert [item["id"] for item in result["data"]] == [img]

    def test_keyword_and_tag_take_intersection(self, client, auth_headers, db_session):
        hit = _upload(client, auth_headers, "麦当劳的猫")
        other = _upload(client, auth_headers, "阳台的猫")
        _add_tags(client, auth_headers, hit, ["猫猫"])
        _add_tags(client, auth_headers, other, ["猫猫"])
        result = _call(
            db_session, _user(db_session), "search_images", {"tag": "猫猫", "keyword": "麦当劳"}
        )
        assert [item["id"] for item in result["data"]] == [hit]

    def test_no_match_returns_empty(self, client, auth_headers, db_session):
        result = _call(db_session, _user(db_session), "search_images", {"tag": "不存在的标签"})
        assert result["ok"] is True
        assert result["data"] == []
        assert "没有找到" in result["summary"]

    def test_limit_truncates_but_summary_keeps_total(self, client, auth_headers, db_session):
        for i in range(3):
            img = _upload(client, auth_headers, f"批量图{i}")
            _add_tags(client, auth_headers, img, ["批量"])
        result = _call(db_session, _user(db_session), "search_images", {"tag": "批量", "limit": 1})
        assert len(result["data"]) == 1
        assert "找到 3 张" in result["summary"]
        assert "返回前 1 张" in result["summary"]

    def test_only_returns_own_images(self, client, auth_headers, bob, db_session):
        """越权保护：别人的图不能出现在结果里（过滤写在查询条件上，不靠工具自觉）"""
        mine = _upload(client, auth_headers, "我的猫")
        theirs = _upload(client, bob, "别人的猫")
        _add_tags(client, auth_headers, mine, ["猫猫"])
        _add_tags(client, bob, theirs, ["猫猫"])

        result = _call(db_session, _user(db_session), "search_images", {"tag": "猫猫"})
        ids = [item["id"] for item in result["data"]]
        assert ids == [mine]
        assert theirs not in ids


class TestGetImageInfo:
    """get_image_info：单张详情 + 公共图库状态"""

    def test_status_none(self, client, auth_headers, test_image, db_session):
        result = _call(db_session, _user(db_session), "get_image_info", {"image_id": test_image})
        assert result["ok"] is True
        assert result["data"]["public_status"] == "none"
        assert result["data"]["public_id"] is None
        assert "未提交公共图库" in result["summary"]

    def test_status_pending(self, client, auth_headers, test_image, db_session):
        public_id = _submit(client, auth_headers, test_image)
        result = _call(db_session, _user(db_session), "get_image_info", {"image_id": test_image})
        assert result["data"]["public_status"] == "pending"
        assert result["data"]["public_id"] == public_id
        assert "审核中" in result["summary"]

    def test_status_approved(self, client, auth_headers, test_image, admin_headers, db_session):
        public_id = _submit(client, auth_headers, test_image)
        r = client.post(
            f"/api/public/images/{public_id}/review",
            headers=admin_headers,
            json={"action": "approve"},
        )
        assert r.status_code == 200, r.text
        result = _call(db_session, _user(db_session), "get_image_info", {"image_id": test_image})
        assert result["data"]["public_status"] == "approved"

    def test_status_rejected(self, client, auth_headers, test_image, admin_headers, db_session):
        public_id = _submit(client, auth_headers, test_image)
        r = client.post(
            f"/api/public/images/{public_id}/review",
            headers=admin_headers,
            json={"action": "reject"},
        )
        assert r.status_code == 200, r.text
        result = _call(db_session, _user(db_session), "get_image_info", {"image_id": test_image})
        assert result["data"]["public_status"] == "rejected"

    def test_other_users_image_denied(self, client, auth_headers, bob, db_session):
        theirs = _upload(client, bob, "别人的图")
        result = _call(db_session, _user(db_session), "get_image_info", {"image_id": theirs})
        assert result["ok"] is False
        assert "不属于当前用户" in result["error"]


class TestSubmitToPublic:
    """submit_to_public：只校验、不写库（human-in-the-loop 的结构保证）"""

    def test_prepare_only_validates_without_writing(
        self, client, auth_headers, test_image, db_session
    ):
        before = db_session.query(PublicImage).count()
        result = _call(db_session, _user(db_session), "submit_to_public", {"image_id": test_image})
        assert result["ok"] is True
        assert result["requires_confirmation"] is True
        assert result["data"]["image_id"] == test_image
        # 工具跑完，公共图库一条记录都不该多出来
        assert db_session.query(PublicImage).count() == before

    def test_defaults_tags_from_personal(self, client, auth_headers, test_image, db_session):
        """不指定标签时，用该图的个人标签预填（与前端提交面板体验一致）"""
        _add_tags(client, auth_headers, test_image, ["猫猫", "橘色"])
        result = _call(db_session, _user(db_session), "submit_to_public", {"image_id": test_image})
        assert set(result["data"]["tags"]) == {"猫猫", "橘色"}

    def test_explicit_tags_are_normalized(self, client, auth_headers, test_image, db_session):
        result = _call(
            db_session,
            _user(db_session),
            "submit_to_public",
            {"image_id": test_image, "tags": ["#猫猫", " 猫猫 ", "橘色"]},
        )
        assert result["data"]["tags"] == ["猫猫", "橘色"]

    def test_duplicate_submission_rejected(self, client, auth_headers, test_image, db_session):
        _submit(client, auth_headers, test_image)
        result = _call(db_session, _user(db_session), "submit_to_public", {"image_id": test_image})
        assert result["ok"] is False
        assert "已提交过公共图库" in result["summary"]

    def test_too_many_tags_rejected(self, client, auth_headers, test_image, db_session):
        """沿用 tag_service 的上限校验：超过 20 个标签要拦在入口"""
        result = _call(
            db_session,
            _user(db_session),
            "submit_to_public",
            {"image_id": test_image, "tags": [f"标签{i}" for i in range(21)]},
        )
        assert result["ok"] is False
        assert "20" in result["summary"]

    def test_nonexistent_image_denied(self, client, auth_headers, db_session):
        result = _call(db_session, _user(db_session), "submit_to_public", {"image_id": 999999})
        assert result["ok"] is False
        assert "不存在" in result["summary"]

    def test_other_users_image_denied(self, client, auth_headers, bob, db_session):
        theirs = _upload(client, bob, "别人的图")
        result = _call(db_session, _user(db_session), "submit_to_public", {"image_id": theirs})
        assert result["ok"] is False
        assert "不属于当前用户" in result["summary"]


class TestArgumentHandling:
    """模型给的参数不可信：任何解析失败都转成可读错误，不能 500 也不能中断对话"""

    def test_invalid_json(self, client, auth_headers, db_session):
        result = execute_tool("search_images", "{不是 json", db_session, _user(db_session))
        assert result["ok"] is False
        assert "不是合法 JSON" in result["error"]

    def test_non_object_json(self, client, auth_headers, db_session):
        result = execute_tool("search_images", "[1, 2]", db_session, _user(db_session))
        assert result["ok"] is False
        assert "必须是 JSON 对象" in result["error"]

    def test_missing_required_field(self, client, auth_headers, db_session):
        result = execute_tool("get_image_info", "{}", db_session, _user(db_session))
        assert result["ok"] is False
        assert "工具参数校验失败" in result["error"]

    def test_unknown_tool(self, client, auth_headers, db_session):
        result = execute_tool("delete_all_images", "{}", db_session, _user(db_session))
        assert result["ok"] is False
        assert "未知工具" in result["error"]

    def test_empty_arguments_means_no_filter(self, client, auth_headers, db_session):
        img = _upload(client, auth_headers, "随便一张")
        result = execute_tool("search_images", "", db_session, _user(db_session))
        assert result["ok"] is True
        assert img in [item["id"] for item in result["data"]]


class TestToolLoop:
    """循环集成：模型要工具 → 本地执行 → 结果回灌 → 继续生成（单次 HTTP 请求内闭环）"""

    @respx.mock
    def test_search_then_answer(self, client, auth_headers, mock_models):
        img = _upload(client, auth_headers, "麦当劳的猫")
        _add_tags(client, auth_headers, img, ["猫猫"])
        route = respx.post(DEEPSEEK_URL).mock(side_effect=[
            httpx.Response(200, text=_tool_call_frames([{
                "id": "call_1",
                "name": "search_images",
                "arguments": json.dumps({"tag": "猫猫"}, ensure_ascii=False),
            }])),
            httpx.Response(200, text=_text_frames("你图库里有一张猫猫的图")),
        ])

        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "我图库里有猫猫的图吗"}],
                "model": "tool-model",
            },
        )
        assert r.status_code == 200, r.text
        events = _parse_sse(r.text)

        calls = _of_type(events, "tool_call")
        assert len(calls) == 1
        assert calls[0]["name"] == "search_images"
        # 分片 arguments 必须拼接成完整 JSON，而不是被后到的分片覆盖
        assert calls[0]["args"] == {"tag": "猫猫"}

        results = _of_type(events, "tool_result")
        assert len(results) == 1
        assert results[0]["ok"] is True
        assert "找到 1 张" in results[0]["summary"]
        assert results[0]["data"][0]["id"] == img
        # 空 content 前导片不该被当成回复内容
        assert _chunks_of(events) == ["你图库里有一张猫猫的图"]

        # 首次请求：带 system prompt + 工具声明
        first = json.loads(route.calls[0].request.content)
        assert first["messages"][0]["role"] == "system"
        assert [t["function"]["name"] for t in first["tools"]] == TOOL_NAMES
        assert first["tool_choice"] == "auto"
        # 第二次请求：assistant(tool_calls) 与 role=tool 结果成对回灌
        second = json.loads(route.calls[1].request.content)
        assert [m["role"] for m in second["messages"]][-2:] == ["assistant", "tool"]
        assert second["messages"][-1]["tool_call_id"] == "call_1"

    @respx.mock
    def test_submit_returns_confirm_without_writing(
        self, client, auth_headers, test_image, mock_models, db_session
    ):
        before = db_session.query(PublicImage).count()
        respx.post(DEEPSEEK_URL).mock(side_effect=[
            httpx.Response(200, text=_tool_call_frames([{
                "id": "call_1",
                "name": "submit_to_public",
                "arguments": json.dumps({"image_id": test_image}),
            }])),
            httpx.Response(200, text=_text_frames("请在确认卡片上点击确认")),
        ])

        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "帮我把这张图提交到公共库"}],
                "model": "tool-model",
            },
        )
        assert r.status_code == 200, r.text
        events = _parse_sse(r.text)

        confirms = _of_type(events, "confirm")
        assert len(confirms) == 1
        assert confirms[0]["action"] == "submit_to_public"
        assert confirms[0]["payload"]["image_id"] == test_image
        assert "请在确认卡片上点击确认" in "".join(_chunks_of(events))
        # 关键：AI 只准备、不落库，授权由用户点确认卡片给出
        assert db_session.query(PublicImage).count() == before

    @respx.mock
    def test_two_consecutive_tool_rounds(self, client, auth_headers, mock_models):
        img = _upload(client, auth_headers, "麦当劳的猫")
        _add_tags(client, auth_headers, img, ["猫猫"])
        respx.post(DEEPSEEK_URL).mock(side_effect=[
            httpx.Response(200, text=_tool_call_frames([{
                "id": "call_1",
                "name": "search_images",
                "arguments": json.dumps({"tag": "猫猫"}, ensure_ascii=False),
            }])),
            httpx.Response(200, text=_tool_call_frames([{
                "id": "call_2",
                "name": "get_image_info",
                "arguments": json.dumps({"image_id": img}),
            }])),
            httpx.Response(200, text=_text_frames("它还没有提交到公共图库")),
        ])

        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "那张猫的图提交过公共库吗"}],
                "model": "tool-model",
            },
        )
        events = _parse_sse(r.text)
        assert [c["name"] for c in _of_type(events, "tool_call")] == [
            "search_images",
            "get_image_info",
        ]
        results = _of_type(events, "tool_result")
        assert results[-1]["data"]["public_status"] == "none"
        assert "它还没有提交到公共图库" in "".join(_chunks_of(events))

    @respx.mock
    def test_step_limit_forces_final_answer(self, client, auth_headers, mock_models):
        """模型反复要工具：用尽步数后去掉 tools 再问一次，强制它基于已有信息作答"""
        stuck = _tool_call_frames([{
            "id": "call_1",
            "name": "search_images",
            "arguments": json.dumps({"tag": "猫猫"}, ensure_ascii=False),
        }])
        responses = [
            httpx.Response(200, text=stuck) for _ in range(AGENT_MAX_TOOL_STEPS)
        ] + [httpx.Response(200, text=_text_frames("根据已有信息，我找到了这张图"))]
        route = respx.post(DEEPSEEK_URL).mock(side_effect=responses)

        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "找找我的猫猫图"}],
                "model": "tool-model",
            },
        )
        assert r.status_code == 200, r.text
        assert route.call_count == AGENT_MAX_TOOL_STEPS + 1
        # 收尾那一次请求不带工具，模型只能回答
        final_body = json.loads(route.calls[-1].request.content)
        assert "tools" not in final_body
        assert "根据已有信息，我找到了这张图" in "".join(_chunks_of(_parse_sse(r.text)))

    @respx.mock
    def test_tool_failure_does_not_break_conversation(self, client, auth_headers, mock_models):
        """工具失败只能变成一条 tool 结果，不能让整段对话报废"""
        respx.post(DEEPSEEK_URL).mock(side_effect=[
            httpx.Response(200, text=_tool_call_frames([{
                "id": "call_1",
                "name": "get_image_info",
                "arguments": json.dumps({"image_id": 999999}),
            }])),
            httpx.Response(200, text=_text_frames("这张图不在你的图库里")),
        ])
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "看看 999999 号图"}],
                "model": "tool-model",
            },
        )
        assert r.status_code == 200, r.text
        events = _parse_sse(r.text)
        results = _of_type(events, "tool_result")
        assert results[0]["ok"] is False
        assert "不存在" in results[0]["summary"]
        assert "这张图不在你的图库里" in "".join(_chunks_of(events))
        assert r.text.rstrip().endswith("data: [DONE]")

    @respx.mock
    def test_identical_tool_calls_executed_once(
        self, client, auth_headers, mock_models, monkeypatch
    ):
        """同一轮里模型重复要同一个工具 + 同一参数：只执行一次，结果复用"""
        executed: list[str] = []
        real_execute = agent_service.execute_tool

        def _spy(name, raw_arguments, db, user):
            executed.append(name)
            return real_execute(name, raw_arguments, db, user)

        monkeypatch.setattr(agent_service, "execute_tool", _spy)

        same_args = json.dumps({"tag": "猫猫"}, ensure_ascii=False)
        respx.post(DEEPSEEK_URL).mock(side_effect=[
            httpx.Response(200, text=_tool_call_frames([
                {"id": "call_1", "name": "search_images", "arguments": same_args},
                {"id": "call_2", "name": "search_images", "arguments": same_args},
            ])),
            httpx.Response(200, text=_text_frames("没有找到猫猫的图")),
        ])
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "找找我的猫猫图"}],
                "model": "tool-model",
            },
        )
        assert r.status_code == 200, r.text
        assert executed == ["search_images"]
        assert len(_of_type(_parse_sse(r.text), "tool_result")) == 2


class TestModelToolFlag:
    """D3：模型兼容性靠显式标记，未标记即降级为普通对话"""

    def test_flag_lookup(self, mock_models):
        assert agent_service.model_supports_tools("tool-model") is True
        assert agent_service.model_supports_tools("text-model") is False
        assert agent_service.model_supports_tools("not-exist") is False

    @respx.mock
    def test_unmarked_model_omits_tools(self, client, auth_headers, mock_models):
        """未标记的模型：请求体里没有 tools 字段，也没有 system prompt 注入（行为不变）"""
        route = respx.post(DEEPSEEK_URL).mock(
            return_value=httpx.Response(200, text=_text_frames("你好"))
        )
        r = client.post(
            "/api/agent/chat",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}], "model": "text-model"},
        )
        assert r.status_code == 200
        body = json.loads(route.calls.last.request.content)
        assert "tools" not in body
        assert "tool_choice" not in body
        assert body["messages"][0]["role"] == "user"

    @respx.mock
    async def test_marked_model_streams_tool_calls(self, mock_models):
        """`iter_llm_stream` 层：分片工具调用被归并成单个 tool_calls 事件"""
        respx.post(DEEPSEEK_URL).mock(return_value=httpx.Response(
            200,
            text=_tool_call_frames([{
                "id": "call_1",
                "name": "search_images",
                "arguments": json.dumps({"tag": "猫猫"}, ensure_ascii=False),
            }]),
        ))

        events = [
            event
            async for event in agent_service.iter_llm_stream(
                "tool-model", [{"role": "user", "content": "hi"}]
            )
        ]
        assert len(events) == 1
        assert events[0]["type"] == "tool_calls"
        call = events[0]["tool_calls"][0]
        assert call["id"] == "call_1"
        assert call["function"]["name"] == "search_images"
        assert json.loads(call["function"]["arguments"]) == {"tag": "猫猫"}
