import { expect, test } from "@playwright/test"
import { loginUser, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程3：详情页编辑（旋转→另存为新图→图库多一张）", async ({ page }) => {
    const username = uniqueName("e2e3")
    const imgName = uniqueName("img3")

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")
    await uploadWithName(page, imgName)

    // 双击卡片进入详情页
    await page.goto("/gallery")
    const card = page.locator(".image-grid .card").filter({ hasText: imgName })
    await card.dblclick()
    await page.waitForURL("**/detail/**")

    // 旋转 → 保存 → 另存为新图
    await page.getByRole("button", { name: "旋转 90°" }).click()
    await page.getByRole("button", { name: "保存修改" }).click()
    await page.getByRole("button", { name: "另存为新图" }).click()

    // 跳回图库，应多一张「原名(编辑)」
    await page.waitForURL("**/gallery")
    await expect(page.locator(".image-grid").getByText(`${imgName}(编辑)`)).toBeVisible()
})
