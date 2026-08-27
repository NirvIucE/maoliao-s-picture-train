import { expect, type Page } from "@playwright/test"

// 唯一用户名/图片名：时间戳后缀，支持重复运行不冲突
export function uniqueName(prefix: string): string {
    return `${prefix}_${Date.now().toString().slice(-8)}`
}

// E2E 专用管理员（由 scripts/e2e_setup.py 种子）
export const ADMIN = { username: "e2e_admin", password: "Admin1234!" }

// 1x1 红色 PNG（base64，免磁盘 fixture）
export const TEST_PNG = {
    name: "e2e_test.png",
    mimeType: "image/png",
    buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64"
    ),
}

// 注册新用户（注册成功页延迟 1.5s 后跳转登录页）
export async function registerUser(page: Page, username: string, password: string, email: string) {
    await page.goto("/register")
    const form = page.locator("form")
    await form.locator('input[type="text"]').fill(username)
    await form.locator('input[type="email"]').fill(email)
    await form.locator('input[type="password"]').fill(password)
    await page.getByRole("button", { name: "注册" }).click()
    await expect(page.getByText("注册成功！正在跳转登录...")).toBeVisible()
    await page.waitForURL("**/login")
}

// 登录并等待跳转到图库
export async function loginUser(page: Page, username: string, password: string) {
    await page.goto("/login")
    const form = page.locator("form")
    await form.locator('input[type="text"]').fill(username)
    await form.locator('input[type="password"]').fill(password)
    await page.getByRole("button", { name: "登录" }).click()
    await page.waitForURL("**/gallery")
}

// 登出（NavBar 按钮）
export async function logout(page: Page) {
    await page.getByRole("button", { name: "登出" }).click()
    await page.waitForURL("**/login")
}

// 上传图片（自定义名），等待成功提示
export async function uploadWithName(page: Page, customName: string) {
    await page.goto("/upload")
    await page.getByPlaceholder("可选，自定义图片名称").fill(customName)
    await page.locator('input[type="file"]').setInputFiles(TEST_PNG)
    await page.locator(".file-row button").click()
    await expect(page.getByText(`"${customName}"上传成功`)).toBeVisible()
}
