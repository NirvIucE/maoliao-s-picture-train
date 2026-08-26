"""
冒烟测试：主链路 happy path，~30 秒跑通
注册→登录→/me→上传→列表→提交公共库→admin 审核→公共库可见（见计划 2.2 节）

注：实际端点行为与计划矩阵略有出入，按实际为准：
- 上传/提交公共库返回 200（非 201，路由未显式设 status_code）
- 审核是 POST /{id}/review（非 PATCH）
"""

from io import BytesIO

from PIL import Image as PILImage

def test_smoke_main_flow(client, db_session):
    """主链路一气呵成：任一步失败即冒烟失败，立即修"""
    # ── 1. 健康检查 ──
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    
    # ── 2. 注册普通用户 ──
    r = client.post(
        "/api/auth/register",
        json={"username": "smoker", "email": "smoker@test.com", "password": "pass1234"},
    )
    assert r.status_code == 201, f"注册失败: {r.text}"
    assert r.json()["uid"]

    # ── 3. 登录拿 token（OAuth2 form 提交）──
    r = client.post(
        "/api/auth/login",
        data={"username": "smoker", "password": "pass1234"},
    )
    assert r.status_code == 200, f"登录失败: {r.text}"
    smoker_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ── 4. 获取个人信息 ──
    r = client.get("/api/users/me", headers=smoker_auth)
    assert r.status_code == 200
    assert r.json()["username"] == "smoker"

    # ── 5. 上传图片（内存生成 PNG，不依赖 fixtures 文件）──
    buf = BytesIO()
    PILImage.new("RGB", (10, 10), (255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/images/upload",
        headers=smoker_auth,
        files={"file": ("test.png", buf, "image/png")},
        data={"custom_name": "smoke 测试图"},
    )
    assert r.status_code == 200, f"上传失败: {r.text}"
    image_id = r.json()["id"]

    # ── 6. 图片列表含刚上传的 ──
    r = client.get("/api/images", headers=smoker_auth)
    assert r.status_code == 200
    assert image_id in [it["id"] for it in r.json()["items"]], "列表里找不到刚上传的图"

    # ── 7. 提交到公共库 ──
    r = client.post(
        "/api/public/images",
        headers=smoker_auth,
        json={"image_id": image_id},
    )
    assert r.status_code == 200, f"提交公共库失败: {r.text}"
    public_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # ── 8. admin 审核：注册 admin → 提权 → 登录 → 审核 ──
    r = client.post(
        "/api/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin1234"},
    )
    assert r.status_code == 201, f"admin 注册失败: {r.text}"

    # 提权（同事务；get_cached_user 即使命中也会重查 DB，role 永远最新，无缓存陈旧）
    from src.models.user import User

    admin = db_session.query(User).filter_by(username="admin").first()
    assert admin is not None, "admin 用户未找到"
    admin.role = "admin"
    db_session.commit()

    r = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin1234"},
    )
    assert r.status_code == 200, f"admin 登录失败: {r.text}"
    admin_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post(
        f"/api/public/images/{public_id}/review",
        headers=admin_auth,
        json={"action": "approve", "comment": "smoke 通过"},
    )
    assert r.status_code == 200, f"审核失败: {r.text}"

    # ── 9. 公共库列表含刚审核的图（普通用户视角）──
    r = client.get("/api/public/images", headers=smoker_auth)
    assert r.status_code == 200
    assert public_id in [it["id"] for it in r.json()["items"]], "公共库看不到已审核的图"