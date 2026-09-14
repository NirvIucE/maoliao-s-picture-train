import { expect, test } from "@playwright/test"
import { loginUser, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程6：个人图库标签筛选（卡片标签 + 筛选条 + 与名称搜索叠加）", async ({ page }) => {
    const username = uniqueName("e2e6")
    const taggedImg = uniqueName("img6a")
    const otherImg = uniqueName("img6b")
    const tagName = "e2e筛猫"

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")
    await uploadWithName(page, taggedImg)
    await uploadWithName(page, otherImg)

    // 先在详情页给其中一张打标签
    await page.goto("/gallery")
    await page.locator(".image-grid .card").filter({ hasText: taggedImg }).dblclick()
    await page.waitForURL("**/detail/**")
    await page.locator(".tags-row input").fill(tagName)
    await page.locator(".tags-row input").press("Enter")
    await expect(page.locator(".tags-row .tag-chip", { hasText: tagName })).toBeVisible()

    // 回图库：卡片上应显示标签，筛选条出现该标签且计数为 1
    await page.goto("/gallery")
    const taggedCard = page.locator(".image-grid .card").filter({ hasText: taggedImg })
    const otherCard = page.locator(".image-grid .card").filter({ hasText: otherImg })
    await expect(page.locator(".image-grid .card")).toHaveCount(2)
    await expect(taggedCard.locator(".card-tag", { hasText: `#${tagName}` })).toBeVisible()
    await expect(otherCard.locator(".card-tag")).toHaveCount(0)

    const chip = page.locator(".tag-filter-bar .filter-chip", { hasText: tagName })
    await expect(chip).toContainText("1")

    // 入口一：点卡片上的标签 → 只剩这一张，筛选条 chip 进入选中态
    await taggedCard.locator(".card-tag", { hasText: `#${tagName}` }).click()
    await expect(page.locator(".image-grid .card")).toHaveCount(1)
    await expect(page.locator(".count")).toHaveText("共显示 1 张图片")
    await expect(chip).toHaveClass(/active/)

    // 清除筛选 → 恢复两张
    await page.locator(".filter-clear").click()
    await expect(page.locator(".image-grid .card")).toHaveCount(2)
    await expect(page.locator(".count")).toHaveText("共显示 2 张图片")

    // 入口二：筛选条 chip 选中 / 再次点击取消选中
    await chip.click()
    await expect(page.locator(".image-grid .card")).toHaveCount(1)
    await chip.click()
    await expect(page.locator(".image-grid .card")).toHaveCount(2)

    // 与名称搜索叠加（AND）：名称命中但标签不命中 → 空结果提示
    await page.getByPlaceholder("搜索图片名称...").fill(otherImg)
    await expect(page.locator(".image-grid .card")).toHaveCount(1)
    await chip.click()
    await expect(page.getByText("没有符合条件的图片")).toBeVisible()

    // 空结果里也能一键清除筛选 → 恢复两张
    await page.locator(".link-btn").click()
    await expect(page.locator(".image-grid .card")).toHaveCount(2)
})
