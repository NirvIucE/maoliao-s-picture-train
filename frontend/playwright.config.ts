import { defineConfig } from "@playwright/test"

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
            env: { DB_NAME: "cat_pic_e2e" },
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
