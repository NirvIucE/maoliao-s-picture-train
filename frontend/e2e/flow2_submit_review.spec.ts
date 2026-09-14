import { expect, test } from "@playwright/test"
import { ADMIN, loginUser, logout, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程2：个人标签 → 提交时预填（可增删）→管理员审核通过→公共图库 #标签 搜索可见", async ({ page }) => {
    const username = uniqueName("e2e2")
    const imgName = uniqueName("img2")
    const tagName = "e2e标签"
    // 阶段 19：个人图库标签（私有），与提交时确认的公开标签区分开
    const personalTag = "e2e个人标签"

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")
    await uploadWithName(page, imgName)

    // 阶段 19：先在个人图库详情页打一个私有标签
    await page.goto("/gallery")
    await page.locator(".image-grid .card").filter({ hasText: imgName }).dblclick()
    await page.waitForURL("**/detail/**")
    await page.locator(".tags-row input").fill(personalTag)
    await page.locator(".tags-row input").press("Enter")
    await expect(page.locator(".tags-row .tag-chip", { hasText: personalTag })).toBeVisible()

    // 回图库提交公共库：个人标签应被预填进提交面板，且可增删后再确认
    await page.goto("/gallery")
    const card = page.locator(".image-grid .card").filter({ hasText: imgName })
    await card.getByRole("button", { name: "提交公共库" }).click()
    await expect(card.locator(".pending-tags .tag-chip", { hasText: personalTag })).toBeVisible()
    // 删掉预填的私有标签，换成要公开的标签
    await card.locator(".pending-tags .tag-chip", { hasText: personalTag }).getByTitle("移除标签").click()
    await card.locator(".tag-submit input").fill(tagName)
    await card.locator(".tag-submit input").press("Enter")
    // 逐标签添加模式：输入回车后生成独立 chip
    await expect(card.locator(".pending-tags .tag-chip", { hasText: tagName })).toBeVisible()
    await card.getByRole("button", { name: "确认提交" }).click()
    await expect(card.locator(".submit-msg")).toHaveText("已提交到公共图库，等待审核")

    // 阶段 19：提交只写公开标签，个人图库的私有标签不受影响
    await page.goto("/gallery")
    await page.locator(".image-grid .card").filter({ hasText: imgName }).dblclick()
    await page.waitForURL("**/detail/**")
    await expect(page.locator(".tags-row .tag-chip", { hasText: personalTag })).toBeVisible()

    // 切换管理员账号审核通过
    await page.goto("/gallery")
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
    await page.getByRole("button", { name: "搜索" }).click()
    await expect(page.locator(".grid .name", { hasText: imgName })).toBeVisible()
})
