"""public_images 模块接口测试：提交 / 列表 / 我的 / 待审 / 审核 / 下架 / 详情 / 可见性 / 删除（见计划 3.1 节）

状态码依据实际路由 + public_service：
- submit 成功 200，重复 400，非本人图 404，无 token 401
- list 角色感知：admin 看全部 approved，普通用户看 visible + 自己
- /pending 仅 admin（普通用户 403）
- review：approve/reject 成功 200，非 pending 状态 400，普通用户 403
- remove：approved→rejected 成功 200，非 approved 400
- detail：成功 200 含 is_owner/is_admin，不存在 404
- visibility：owner 或 admin 可改 200，他人 403
- delete：owner 或 admin 可删 200，他人 403
"""

import httpx
import pytest
import respx


# ── 辅助 fixtures ──
@pytest.fixture
def other_user_headers(client):
    """第二个用户 bob 的 auth headers（用于权限隔离测试）"""
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@test.com", "password": "pass1234"},
    )
    r = client.post("/api/auth/login", data={"username": "bob", "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def pending_public_id(client, auth_headers, test_image):
    """alice 上传图后提交公共库 → 返回 public_id（status=pending）"""
    r = client.post("/api/public/images", headers=auth_headers, json={"image_id": test_image})
    assert r.status_code == 200, f"提交失败: {r.text}"
    return r.json()["id"]


@pytest.fixture
def approved_public_id(client, admin_headers, pending_public_id):
    """admin 审核通过 pending_public_id → 返回 public_id（status=approved）"""
    r = client.post(
        f"/api/public/images/{pending_public_id}/review",
        headers=admin_headers,
        json={"action": "approve"},
    )
    assert r.status_code == 200, f"审核失败: {r.text}"
    return pending_public_id


class TestSubmit:
    def test_submit_success(self, client, auth_headers, test_image):
        """提交自己的图 → 200 + status=pending"""
        r = client.post("/api/public/images", headers=auth_headers, json={"image_id": test_image})
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        assert r.json()["image_id"] == test_image

    def test_submit_duplicate(self, client, auth_headers, pending_public_id, test_image):
        """重复提交同一张图 → 400"""
        r = client.post("/api/public/images", headers=auth_headers, json={"image_id": test_image})
        assert r.status_code == 400

    def test_submit_not_owner(self, client, other_user_headers, test_image):
        """bob 提交 alice 的图 → 404（所有权隔离）"""
        r = client.post("/api/public/images", headers=other_user_headers, json={"image_id": test_image})
        assert r.status_code == 404

    def test_submit_unauthorized(self, client, test_image):
        """无 token → 401"""
        r = client.post("/api/public/images", json={"image_id": test_image})
        assert r.status_code == 401


class TestListPublic:
    def test_list_empty(self, client, auth_headers):
        """无 approved 图 → total=0"""
        r = client.get("/api/public/images", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_user_sees_approved(self, client, other_user_headers, approved_public_id):
        """approved 后普通用户 bob 可见 → total>=1"""
        r = client.get("/api/public/images", headers=other_user_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_admin_sees_all(self, client, admin_headers, approved_public_id):
        """admin 看全部 approved → total>=1"""
        r = client.get("/api/public/images", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_search_custom_name(self, client, other_user_headers, approved_public_id):
        """搜索 custom_name 关键词（fixture）→ 命中"""
        r = client.get(
            "/api/public/images",
            headers=other_user_headers,
            params={"search": "fixture"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_search_not_original_name(self, client, other_user_headers, approved_public_id):
        """搜索只按 custom_name：original_name（test.png）不参与匹配 → 不命中"""
        r = client.get(
            "/api/public/images",
            headers=other_user_headers,
            params={"search": "test.png"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestMySubmissions:
    def test_my_submissions(self, client, auth_headers, pending_public_id):
        """我的提交 → 200 + 含 pending 记录"""
        r = client.get("/api/public/images/my", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        assert r.json()["items"][0]["status"] == "pending"


class TestPending:
    def test_pending_admin(self, client, admin_headers, pending_public_id):
        """admin 看待审列表 → 200 + 含记录"""
        r = client.get("/api/public/images/pending", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_pending_user_forbidden(self, client, auth_headers):
        """普通用户访问 /pending → 403"""
        r = client.get("/api/public/images/pending", headers=auth_headers)
        assert r.status_code == 403


class TestReview:
    def test_review_approve(self, client, admin_headers, pending_public_id):
        """admin 通过 → 200 + status=approved"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/review",
            headers=admin_headers,
            json={"action": "approve"},
        )
        assert r.status_code == 200
        r = client.get(f"/api/public/images/{pending_public_id}", headers=admin_headers)
        assert r.json()["status"] == "approved"

    def test_review_reject(self, client, admin_headers, pending_public_id):
        """admin 拒绝 → 200 + status=rejected + comment"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/review",
            headers=admin_headers,
            json={"action": "reject", "comment": "不合格"},
        )
        assert r.status_code == 200
        r = client.get(f"/api/public/images/{pending_public_id}", headers=admin_headers)
        assert r.json()["status"] == "rejected"
        assert r.json()["review_comment"] == "不合格"

    def test_review_not_pending(self, client, admin_headers, approved_public_id):
        """审核已 approved 的记录 → 400"""
        r = client.post(
            f"/api/public/images/{approved_public_id}/review",
            headers=admin_headers,
            json={"action": "approve"},
        )
        assert r.status_code == 400

    def test_review_user_forbidden(self, client, auth_headers, pending_public_id):
        """普通用户审核 → 403"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/review",
            headers=auth_headers,
            json={"action": "approve"},
        )
        assert r.status_code == 403


class TestRemove:
    def test_remove_success(self, client, admin_headers, approved_public_id):
        """admin 下架 approved → 200 + status=rejected"""
        r = client.post(
            f"/api/public/images/{approved_public_id}/remove",
            headers=admin_headers,
            json={"comment": "违规"},
        )
        assert r.status_code == 200
        r = client.get(f"/api/public/images/{approved_public_id}", headers=admin_headers)
        assert r.json()["status"] == "rejected"

    def test_remove_not_approved(self, client, admin_headers, pending_public_id):
        """下架 pending 记录 → 400"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/remove",
            headers=admin_headers,
            json={},
        )
        assert r.status_code == 400


class TestDetail:
    def test_detail_success(self, client, auth_headers, pending_public_id):
        """详情 → 200 + is_owner=True + is_admin=False"""
        r = client.get(f"/api/public/images/{pending_public_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == pending_public_id
        assert r.json()["is_owner"] is True
        assert r.json()["is_admin"] is False

    def test_detail_not_found(self, client, auth_headers):
        """不存在 → 404"""
        r = client.get("/api/public/images/9999", headers=auth_headers)
        assert r.status_code == 404


class TestVisibility:
    def test_visibility_owner(self, client, auth_headers, approved_public_id):
        """owner 切换可见性 → 200"""
        r = client.post(
            f"/api/public/images/{approved_public_id}/visibility",
            headers=auth_headers,
            json={"visible": False},
        )
        assert r.status_code == 200

    def test_visibility_unauthorized(self, client, other_user_headers, approved_public_id):
        """bob 改 alice 的可见性 → 403"""
        r = client.post(
            f"/api/public/images/{approved_public_id}/visibility",
            headers=other_user_headers,
            json={"visible": False},
        )
        assert r.status_code == 403


class TestDelete:
    def test_delete_owner(self, client, auth_headers, pending_public_id):
        """owner 删自己的记录 → 200"""
        r = client.delete(f"/api/public/images/{pending_public_id}", headers=auth_headers)
        assert r.status_code == 200

    def test_delete_admin(self, client, admin_headers, approved_public_id):
        """admin 删任意记录 → 200"""
        r = client.delete(f"/api/public/images/{approved_public_id}", headers=admin_headers)
        assert r.status_code == 200

    def test_delete_unauthorized(self, client, other_user_headers, approved_public_id):
        """bob 删 alice 的记录 → 403"""
        r = client.delete(f"/api/public/images/{approved_public_id}", headers=other_user_headers)
        assert r.status_code == 403


class TestAnonymous:
    """匿名用户（未登录）访问公共图库"""

    def test_anonymous_can_list_approved(self, client, approved_public_id):
        """匿名用户能看 approved+visible 列表 → 200 + total >= 1"""
        r = client.get("/api/public/images")
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        # 返回的条目都是 approved + visible
        for item in r.json()["items"]:
            assert item["status"] == "approved"
            assert item["is_visible"] is True

    def test_anonymous_can_view_detail(self, client, approved_public_id):
        """匿名用户能看 approved+visible 详情 → 200 + is_owner=False + is_admin=False"""
        r = client.get(f"/api/public/images/{approved_public_id}")
        assert r.status_code == 200
        assert r.json()["is_owner"] is False
        assert r.json()["is_admin"] is False

    def test_anonymous_cannot_download(self, client, approved_public_id):
        """匿名用户不能下载 → 401"""
        r = client.get(f"/api/public/images/{approved_public_id}/download")
        assert r.status_code == 401

    def test_logged_in_can_download(self, client, auth_headers, approved_public_id):
        """登录用户能下载 → 200 + 文件流"""
        r = client.get(f"/api/public/images/{approved_public_id}/download", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        assert len(r.content) > 0  # 有文件内容

    def test_anonymous_cannot_see_hidden(self, client, auth_headers, admin_headers, pending_public_id):
        """匿名用户看不到 is_visible=False 的图（先 approve 再隐藏）"""
        # admin 审核通过
        client.post(
            f"/api/public/images/{pending_public_id}/review",
            headers=admin_headers,
            json={"action": "approve"},
        )
        # owner 隐藏
        client.post(
            f"/api/public/images/{pending_public_id}/visibility",
            headers=auth_headers,
            json={"visible": False},
        )
        # 匿名列表里看不到
        r = client.get("/api/public/images")
        ids = [item["id"] for item in r.json()["items"]]
        assert pending_public_id not in ids


class TestTags:
    """阶段 12：公共图库标签（提交带标签 / 添加 / 删除 / 权限 / #严格匹配搜索）"""

    def test_submit_with_tags(self, client, auth_headers, test_image):
        """提交时携带标签 → 200 + 规范化（去#、去空、去重）"""
        r = client.post(
            "/api/public/images",
            headers=auth_headers,
            json={"image_id": test_image, "tags": ["猫", "#风景", " 猫 ", ""]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["猫", "风景"]

    def test_submit_without_tags(self, client, auth_headers, pending_public_id):
        """不带标签提交 → tags 为空列表"""
        r = client.get(f"/api/public/images/{pending_public_id}", headers=auth_headers)
        assert r.json()["tags"] == []

    def test_add_tags_owner(self, client, auth_headers, pending_public_id):
        """owner 添加标签 → 200 + 返回当前全部标签"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["夜景"]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["夜景"]

    def test_add_tags_other_user_forbidden(self, client, other_user_headers, pending_public_id):
        """bob 给 alice 的图加标签 → 403"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=other_user_headers,
            json={"tags": ["x"]},
        )
        assert r.status_code == 403

    def test_add_tags_admin(self, client, admin_headers, pending_public_id):
        """admin 可给任意图加标签 → 200"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=admin_headers,
            json={"tags": ["管理员加的"]},
        )
        assert r.status_code == 200
        assert "管理员加的" in r.json()["tags"]

    def test_remove_tag_owner(self, client, auth_headers, pending_public_id):
        """owner 删除标签 → 200；重复删除 → 404"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        r = client.delete(f"/api/public/images/{pending_public_id}/tags/猫", headers=auth_headers)
        assert r.status_code == 200
        r2 = client.delete(f"/api/public/images/{pending_public_id}/tags/猫", headers=auth_headers)
        assert r2.status_code == 404

    def test_remove_tag_other_user_forbidden(self, client, other_user_headers, pending_public_id):
        """bob 删 alice 的标签 → 403"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=other_user_headers,
            json={"tags": ["猫"]},
        )
        assert client.delete(
            f"/api/public/images/{pending_public_id}/tags/猫", headers=other_user_headers
        ).status_code == 403

    def test_search_tag_exact_match(
        self, client, auth_headers, other_user_headers, approved_public_id
    ):
        """#标签 搜索为严格匹配：#猫 命中标签"猫"；#狸花猫 不命中"""
        client.post(
            f"/api/public/images/{approved_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        r = client.get("/api/public/images", headers=other_user_headers, params={"search": "#猫"})
        assert r.status_code == 200
        assert approved_public_id in [i["id"] for i in r.json()["items"]]
        # 严格匹配：该图没有"狸花猫"标签 → 不命中
        r2 = client.get(
            "/api/public/images",
            headers=other_user_headers,
            params={"search": "#狸花猫"},
        )
        assert r2.status_code == 200
        assert approved_public_id not in [i["id"] for i in r2.json()["items"]]

    def test_search_tag_does_not_affect_normal_search(
        self, client, auth_headers, other_user_headers, approved_public_id
    ):
        """普通关键词搜索不受 # 分支影响：custom_name 仍可命中"""
        client.post(
            f"/api/public/images/{approved_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        # fixture 图的 custom_name 含 "fixture" 前缀
        r = client.get(
            "/api/public/images",
            headers=other_user_headers,
            params={"search": "fixture"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_anonymous_can_search_tag(self, client, auth_headers, approved_public_id):
        """匿名用户可用 #标签 搜索 → 200 + 命中"""
        client.post(
            f"/api/public/images/{approved_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        r = client.get("/api/public/images", params={"search": "#猫"})
        assert r.status_code == 200
        assert approved_public_id in [i["id"] for i in r.json()["items"]]


class TestTagIsolation:
    """阶段 19：个人图库标签（image_tags）与公共图库标签（public_image_tags）两层分离

    隔离要守住两件事：① 隐私不外泄——个人图库的私人归类不会出现在公共图库；
    ② 语义不耦合——两边各自增删标签互不影响。
    """

    def test_submit_writes_only_public_tags(
        self, client, auth_headers, test_image
    ):
        """提交携带标签 → 只写公开标签；个人图库标签保持原样（不自动带入）"""
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["私人"]})
        r = client.post(
            "/api/public/images",
            headers=auth_headers,
            json={"image_id": test_image, "tags": ["公开"]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["公开"]
        detail = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert detail.json()["tags"] == ["私人"]

    def test_public_add_tags_does_not_affect_personal(
        self, client, auth_headers, pending_public_id, test_image
    ):
        """给公共记录加标签 → 个人图库该图标签不受影响"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["公开"]},
        )
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.json()["tags"] == []

    def test_personal_add_tags_does_not_affect_public(
        self, client, auth_headers, pending_public_id, test_image
    ):
        """给个人图库加标签 → 已提交的公开记录标签不受影响"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["公开"]},
        )
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["私人"]})
        r = client.get(f"/api/public/images/{pending_public_id}", headers=auth_headers)
        assert r.json()["tags"] == ["公开"]

    def test_personal_remove_tag_does_not_affect_public(
        self, client, auth_headers, pending_public_id, test_image
    ):
        """删个人标签 → 公开标签仍在（反向也不同步）"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        assert client.delete(
            f"/api/images/{test_image}/tags/猫", headers=auth_headers
        ).status_code == 200
        r = client.get(f"/api/public/images/{pending_public_id}", headers=auth_headers)
        assert r.json()["tags"] == ["猫"]

    def test_public_remove_tag_does_not_affect_personal(
        self, client, auth_headers, pending_public_id, test_image
    ):
        """删公开标签 → 个人标签仍在（隐私保护的核心收益：不会连带删掉私人归类）"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫"]},
        )
        client.post(f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["猫"]})
        assert client.delete(
            f"/api/public/images/{pending_public_id}/tags/猫", headers=auth_headers
        ).status_code == 200
        r = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert r.json()["tags"] == ["猫"]

    def test_personal_only_tag_not_searchable_in_public(
        self, client, auth_headers, other_user_headers, approved_public_id, test_image
    ):
        """只在个人图库打的标签，公共图库 #标签 搜索搜不到（隐私外泄防线）"""
        client.post(
            f"/api/images/{test_image}/tags", headers=auth_headers, json={"tags": ["身份证"]}
        )
        r = client.get(
            "/api/public/images",
            headers=other_user_headers,
            params={"search": "#身份证"},
        )
        assert r.status_code == 200
        assert approved_public_id not in [i["id"] for i in r.json()["items"]]

    def test_resubmit_after_delete_is_independent(
        self, client, auth_headers, pending_public_id, test_image
    ):
        """删除公共记录后重新提交 → 新记录的公开标签独立，且仍不写个人标签"""
        client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["旧标签"]},
        )
        assert client.delete(
            f"/api/public/images/{pending_public_id}", headers=auth_headers
        ).status_code == 200
        r = client.post(
            "/api/public/images",
            headers=auth_headers,
            json={"image_id": test_image, "tags": ["新标签"]},
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["新标签"]
        detail = client.get(f"/api/images/{test_image}", headers=auth_headers)
        assert detail.json()["tags"] == []

    def test_public_tags_validation_400(self, client, auth_headers, pending_public_id):
        """公共图库标签同样受 D4 校验约束（超长 / 超数量 → 400）"""
        r = client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": ["猫" * 51]},
        )
        assert r.status_code == 400
        r2 = client.post(
            f"/api/public/images/{pending_public_id}/tags",
            headers=auth_headers,
            json={"tags": [f"标签{i}" for i in range(21)]},
        )
        assert r2.status_code == 400


class TestAISearch:
    """阶段 13：AI 搜索（语义通道 mock / 识图通道 mock / 幻觉过滤 / 降级）"""

    @staticmethod
    def _mock_text_llm(content: str) -> None:
        """mock 文本模型（deepseek）返回指定 content（SSE 流格式）"""
        respx.post("https://api.deepseek.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                text=(
                    f'data: {{"choices":[{{"delta":{{"content":"{content}"}}}}]}}'
                    "\n\ndata: [DONE]\n\n"
                ),
            )
        )

    @respx.mock
    def test_semantic_hits_and_hallucination_filtered(
        self, client, auth_headers, approved_public_id, mock_models
    ):
        """语义通道：AI 返回 [approved_id, 9999] → 只返回 approved_id（幻觉 9999 被过滤）"""
        self._mock_text_llm(f"[{approved_public_id}, 9999]")
        r = client.post(
            "/api/public/images/ai-search",
            headers=auth_headers,
            json={"query": "猫", "mode": "semantic"},
        )
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert approved_public_id in ids
        assert 9999 not in ids

    @respx.mock
    def test_semantic_invalid_json_returns_empty(
        self, client, auth_headers, approved_public_id, mock_models
    ):
        """AI 返回非法内容 → 空结果（不崩溃）"""
        self._mock_text_llm("我不太确定")
        r = client.post(
            "/api/public/images/ai-search",
            headers=auth_headers,
            json={"query": "猫"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_no_model_returns_503(self, client, auth_headers, approved_public_id, monkeypatch):
        """无 AI 模型配置 → 503"""
        monkeypatch.setattr("src.services.public_service.MODEL_REGISTRY", [])
        r = client.post(
            "/api/public/images/ai-search",
            headers=auth_headers,
            json={"query": "猫"},
        )
        assert r.status_code == 503

    def test_empty_query_400(self, client, auth_headers):
        """空搜索词 → 400"""
        r = client.post(
            "/api/public/images/ai-search",
            headers=auth_headers,
            json={"query": "  "},
        )
        assert r.status_code == 400

    @respx.mock
    def test_vision_channel_hit(self, client, auth_headers, approved_public_id, mock_models):
        """识图通道：视觉模型回答"是" → 命中"""
        respx.post("https://api.siliconflow.cn/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"是"}}]}\n\ndata: [DONE]\n\n',
            )
        )
        r = client.post(
            "/api/public/images/ai-search",
            headers=auth_headers,
            json={"query": "猫", "mode": "vision"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    @respx.mock
    def test_anonymous_ai_search(self, client, approved_public_id, mock_models):
        """匿名用户可用 AI 搜索（无需登录）"""
        self._mock_text_llm(f"[{approved_public_id}]")
        r = client.post(
            "/api/public/images/ai-search",
            json={"query": "猫"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1
