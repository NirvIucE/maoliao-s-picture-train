import { expect, test } from "@playwright/test"
import { loginUser, registerUser, TEST_PNG, uniqueName } from "./utils"

test("流程5：AI 助手工具调用（步骤行 + 确认卡片真正落库）", async ({ page }) => {
    const username = uniqueName("e2e5")
    const imageName = "AI 待提交图"

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")

    // 先真实上传一张图：确认卡片要引用一个真实存在的 image_id，点确认才会真的写库
    await page.goto("/upload")
    await page.getByPlaceholder("可选，自定义图片名称").fill(imageName)
    await page.locator('input[type="file"]').setInputFiles(TEST_PNG)
    const uploadDone = page.waitForResponse(
        (r) =>
            r.url().includes("/api/images/upload") &&
            r.request().method() === "POST" &&
            r.status() === 200
    )
    await page.locator(".file-row button").click()
    await expect(page.getByText(`"${imageName}"上传成功`)).toBeVisible()
    const imageId = (await (await uploadDone).json()).id as number

    // mock 对话流：工具调用 → 检索结果 → 确认事件 → 收尾文本
    // （只 mock 模型那一层，确认卡片触发的 POST /api/public/images 仍走真实后端）
    await page.route("**/api/agent/chat", async (route) => {
        const body = [
            'data: {"type":"tool_call","name":"search_images","args":{"tag":"猫猫"}}\n\n',
            `data: ${JSON.stringify({
                type: "tool_result",
                name: "search_images",
                ok: true,
                summary: "找到 1 张",
                data: [
                    {
                        id: imageId,
                        display_name: imageName,
                        tags: ["猫猫"],
                        created_at: "2026-09-14",
                        thumbnail_url: null,
                    },
                ],
            })}\n\n`,
            `data: ${JSON.stringify({
                type: "confirm",
                action: "submit_to_public",
                payload: { image_id: imageId, display_name: imageName, tags: ["猫猫"] },
            })}\n\n`,
            'data: {"chunk":"请在下方卡片上确认提交。"}\n\n',
            "data: [DONE]\n\n",
        ].join("")
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            headers: { "Cache-Control": "no-cache" },
            body,
        })
    })

    await page.goto("/agent")
    await page.getByPlaceholder("输入消息，或上传图片让我分析...").fill("把那张猫猫的图提交到公共图库")
    await page.getByRole("button", { name: "发送" }).click()

    // 工具步骤行：检索到了什么，用户看得见
    const assistant = page.locator(".message.assistant").last()
    await expect(assistant.locator(".tool-step")).toHaveCount(1)
    await expect(assistant.locator(".tool-step")).toContainText("检索个人图库")
    await expect(assistant.locator(".tool-step")).toContainText("找到 1 张")
    await expect(assistant).toContainText("请在下方卡片上确认提交。")

    // 确认卡片：AI 只准备参数，授权由用户点击给出
    const card = assistant.locator(".confirm-card")
    await expect(card).toContainText(imageName)
    await expect(card).toContainText("猫猫")

    const submitted = page.waitForResponse(
        (r) => r.url().includes("/api/public/images") && r.request().method() === "POST"
    )
    await card.getByRole("button", { name: "确认提交" }).click()
    expect((await submitted).status()).toBe(200)

    // 提交成功：助手消息追加结果，卡片按钮转为「已提交」且不可再点（防重复提交）
    await expect(assistant).toContainText(`已提交《${imageName}》，等待管理员审核。`)
    await expect(card.getByRole("button", { name: "已提交" })).toBeDisabled()
})
