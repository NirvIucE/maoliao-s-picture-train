import { expect, test } from "@playwright/test"
import { ADMIN, loginUser, logout, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程2：提交公共库（带标签）→管理员审核通过→公共图库 #标签 搜索可见", async ({ page }) => {
    const username = uniqueName("e2e2")
    const imgName = uniqueName("img2")
    const tagName = "e2e标签"

    // 普通用户上传并提交公共库（阶段 12：提交时携带标签）
    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")
    await uploadWithName(page, imgName)

    await page.goto("/gallery")
    const card = page.locator(".image-grid .card").filter({ hasText: imgName })
    await card.getByRole("button", { name: "提交公共库" }).click()
    await card.locator(".tag-submit input").fill(tagName)
    await card.locator(".tag-submit input").press("Enter")
    // 逐标签添加模式：输入回车后生成独立 chip
    await expect(card.locator(".pending-tags .tag-chip", { hasText: tagName })).toBeVisible()
    await card.getByRole("button", { name: "确认提交" }).click()
    await expect(card.locator(".submit-msg")).toHaveText("已提交到公共图库，等待审核")

    // 切换管理员账号审核通过
    await logout(page)
    await loginUser(page, ADMIN.username, ADMIN.password)
    await page.goto("/admin/review")
    const item = page.locator(".item").filter({ hasText: imgName })
    await item.getByRole("button", { name: "通过" }).click()
    await expect(page.getByText("已通过审核")).toBeVisible()

    // 匿名访问公共图库，用 #标签 严格匹配搜索应能看到
    await logout(page)
    await page.goto("/public")
    await page.getByPlaceholder(/搜索图片名称/).fill(`#${tagName}`)
    await expect(page.locator(".grid .name", { hasText: imgName })).toBeVisible()
})
