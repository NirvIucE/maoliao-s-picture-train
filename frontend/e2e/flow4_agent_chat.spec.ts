import { expect, test } from "@playwright/test"
import { loginUser, registerUser, TEST_PNG, uniqueName } from "./utils"

test("流程4：AI 对话（选图→发消息→流式响应显示）", async ({ page }) => {
    const username = uniqueName("e2e4")

    // mock AI 对话流式接口，不调用真实模型（确定性验证 UI 流式渲染链路）
    await page.route("**/api/agent/chat", async (route) => {
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            headers: { "Cache-Control": "no-cache" },
            body: 'data: {"chunk":"你好，"}\n\ndata: {"chunk":"我是猫里奥AI助手"}\n\ndata: [DONE]\n',
        })
    })

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")

    // 进入 AI 助手，本地上传图片作为附件
    await page.goto("/agent")
    await page.locator('input[type="file"]').setInputFiles(TEST_PNG)
    await expect(page.locator(".image-preview")).toBeVisible()

    // 发送消息
    await page.getByPlaceholder("输入消息，或上传图片让我分析...").fill("分析这张图片")
    await page.getByRole("button", { name: "发送" }).click()

    // 流式响应逐段渲染在助手消息中
    const assistant = page.locator(".message.assistant").last()
    await expect(assistant).toContainText("你好，")
    await expect(assistant).toContainText("我是猫里奥AI助手")
})
