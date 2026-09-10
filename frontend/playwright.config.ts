import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig } from "@playwright/test"

// E2E 专用上传目录（与真实 backend/src/uploads 完全分离）
// 背景：此前 E2E 只隔离了数据库，上传的图片仍写进真实 uploads，堆下测试孤儿文件
const E2E_UPLOAD_ROOT = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../backend/e2e-uploads"
)

export default defineConfig({
    testDir: "./e2e",
    timeout: 60_000,
    expect: { timeout: 10_000 },
    // E2E 共享同一个后端测试库，串行执行避免数据互相干扰
    fullyParallel: false,
    workers: 1,
    retries: 0,
    reporter: [["list"]],
    use: {
        baseURL: "http://localhost:5173",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
    },
    webServer: [
        {
            // 后端：先准备 E2E 专用库（建库 + 迁移 + 种子 admin），再启动 uvicorn
            command: "uv run python scripts/e2e_setup.py && uv run uvicorn src.main:app --port 8000",
            cwd: "../backend",
            env: { DB_NAME: "cat_pic_e2e", UPLOAD_ROOT: E2E_UPLOAD_ROOT },
            url: "http://localhost:8000/health",
            reuseExistingServer: false,
            timeout: 120_000,
        },
        {
            command: "npm run dev",
            cwd: ".",
            url: "http://localhost:5173",
            reuseExistingServer: false,
            timeout: 60_000,
        },
    ],
})
