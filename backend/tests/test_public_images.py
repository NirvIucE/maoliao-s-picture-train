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

import pytest


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
