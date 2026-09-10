"""
猫里奥全栈云图库 — Locust 压测脚本（见计划第 4 节）

使用方法：
1. 安装 locust:  pip install locust
2. 启动后端:     cd backend && uv run uvicorn src.main:app --port 8000
3. 启动 locust:  cd tests/perf && locust -f locustfile.py
4. 浏览器打开:   http://localhost:8089

压测场景（5 个，按权重分配）：
- 图片列表（缓存命中）×5     → 验证 Redis GET + ORM 序列化
- 图片列表+搜索（缓存 miss）×3 → 验证 DB 查询 + 索引
- 公共图库 ×2                 → 验证角色感知查询
- 登录 ×1                     → 验证 bcrypt CPU 瓶颈
- 上传 ×1                     → 验证文件 IO + 缩略图生成
"""

import io
import os

from locust import HttpUser, between, task
from PIL import Image

# 压测图边长（阶段 18 并发治理：验证大图上传对事件循环的阻塞程度）
# 默认 100（小图基线）；大图场景用 STRESS_IMG_SIZE=3000 覆盖
STRESS_IMG_SIZE = int(os.getenv("STRESS_IMG_SIZE", "100"))


class WebsiteUser(HttpUser):
    """模拟真实用户：注册→登录→浏览图片→偶尔上传"""

    # 每个虚拟用户请求间隔 1~3 秒（模拟人类思考时间）
    wait_time = between(1, 3)

    # 后端地址（locust 会提示用 --host 覆盖）
    host = "http://localhost:8000"

    def on_start(self):
        """每个虚拟用户启动时：注册 + 登录拿 token"""
        self.username = f"loadtest_{id(self)}"
        # 注册（可能 409 如果重复跑，忽略即可）
        self.client.post(
            "/api/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@test.com",
                "password": "pass1234",
            },
        )
        # 登录拿 token
        r = self.client.post(
            "/api/auth/login",
            data={"username": self.username, "password": "pass1234"},
            name="/api/auth/login [on_start]",
        )
        self.token = r.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_images(self):
        """图片列表（高频，验证缓存效果）"""
        self.client.get("/api/images", headers=self.headers, name="/api/images [缓存命中]")

    @task(3)
    def list_images_with_search(self):
        """图片列表 + 搜索（缓存 miss 路径，每次关键词不同）"""
        import random

        keyword = random.choice(["test", "a", "b", "c", "img"])
        self.client.get(
            f"/api/images?search={keyword}",
            headers=self.headers,
            name="/api/images?search [缓存miss]",
        )

    @task(2)
    def public_gallery(self):
        """公共图库（角色感知查询，需登录）"""
        self.client.get("/api/public/images", headers=self.headers, name="/api/public/images")

    @task(1)
    def login(self):
        """登录（bcrypt CPU 密集型，验证单核瓶颈）"""
        self.client.post(
            "/api/auth/login",
            data={"username": self.username, "password": "pass1234"},
            name="/api/auth/login [bcrypt]",
        )

    @task(1)
    def upload_image(self):
        """上传图片（IO 密集 + CPU 密集：文件保存 + 缩略图生成）

        小图（默认 100px）测吞吐；大图（STRESS_IMG_SIZE=3000）用来暴露
        「缩略图 CPU 阻塞事件循环 → 拖垮其它端点」的 P0-1 问题。
        """
        buf = io.BytesIO()
        Image.new("RGB", (STRESS_IMG_SIZE, STRESS_IMG_SIZE), (255, 0, 0)).save(buf, "PNG")
        buf.seek(0)
        self.client.post(
            "/api/images/upload",
            headers=self.headers,
            files={"file": ("stress.png", buf, "image/png")},
            name=f"/api/images/upload [{STRESS_IMG_SIZE}px]",
        )
