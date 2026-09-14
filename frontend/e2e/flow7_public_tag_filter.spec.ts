import { expect, test } from "@playwright/test"
import { ADMIN, loginUser, logout, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程7：公共图库标签筛选（筛选条 + 卡片标签 + 与名称搜索叠加）", async ({ page }) => {
    const username = uniqueName("e2e7")
    const taggedImg = uniqueName("img7a")
    const otherImg = uniqueName("img7b")
    // 标签名带时间戳：公共图库是全站共享数据，用唯一标签才能把筛选结果隔离出来
    const tagName = uniqueName("e2e公筛")

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")
    await uploadWithName(page, taggedImg)
    await uploadWithName(page, otherImg)

    // 两张都提交公共库，只有一张带标签（另一个用于验证 tag + search 的 AND）
    await page.goto("/gallery")
    const cardA = page.locator(".image-grid .card").filter({ hasText: taggedImg })
    await cardA.getByRole("button", { name: "提交公共库" }).click()
    await cardA.locator(".tag-submit input").fill(tagName)
    await cardA.locator(".tag-submit input").press("Enter")
    await expect(cardA.locator(".pending-tags .tag-chip", { hasText: tagName })).toBeVisible()
    await cardA.getByRole("button", { name: "确认提交" }).click()
    await expect(cardA.locator(".submit-msg")).toHaveText("已提交到公共图库，等待审核")

    const cardB = page.locator(".image-grid .card").filter({ hasText: otherImg })
    await cardB.getByRole("button", { name: "提交公共库" }).click()
    await cardB.getByRole("button", { name: "确认提交" }).click()
    await expect(cardB.locator(".submit-msg")).toHaveText("已提交到公共图库，等待审核")

    // 切管理员审核通过两张（审核后该条从待审列表消失，以此确认操作已生效）
    await logout(page)
    await loginUser(page, ADMIN.username, ADMIN.password)
    await page.goto("/admin/review")
    for (const name of [taggedImg, otherImg]) {
        const item = page.locator(".item").filter({ hasText: name })
        await item.getByRole("button", { name: "通过" }).click()
        await expect(item).toHaveCount(0)
    }

    // 匿名访问公共图库：筛选条应出现该标签且计数为 1（公开库是全站数据，故只断言自己的标签）
    await logout(page)
    await page.goto("/public")
    const chip = page.locator(".tag-filter-bar .filter-chip", { hasText: tagName })
    await expect(chip).toBeVisible()
    await expect(chip).toContainText("1")

    // 入口一：点卡片上的标签 → 只剩带该标签的那张，chip 进入选中态
    const taggedCard = page.locator(".grid .card").filter({ hasText: taggedImg })
    await taggedCard.locator(".tag-chip", { hasText: `#${tagName}` }).click()
    await expect(page.locator(".count")).toHaveText("共 1 张图片")
    await expect(chip).toHaveClass(/active/)

    // 清除筛选 → 该标签不再选中，带标签的图恢复可见
    await page.locator(".filter-clear").click()
    await expect(chip).not.toHaveClass(/active/)
    await expect(taggedCard).toBeVisible()

    // 入口二：筛选条 chip 选中 / 再次点击取消选中
    await chip.click()
    await expect(page.locator(".count")).toHaveText("共 1 张图片")
    await chip.click()
    await expect(chip).not.toHaveClass(/active/)
    await expect(taggedCard).toBeVisible()

    // 与名称搜索叠加（AND）：另一张图名称命中但没有该标签 → 空结果提示
    await chip.click()
    await page.getByPlaceholder(/搜索图片名称/).fill(otherImg)
    await page.getByRole("button", { name: "搜索" }).click()
    await expect(page.getByText("没有符合条件的图片")).toBeVisible()

    // 空结果里一键清除筛选 → 带标签的图恢复可见
    await page.locator(".link-btn").click()
    await expect(chip).not.toHaveClass(/active/)
    await expect(taggedCard).toBeVisible()
})
