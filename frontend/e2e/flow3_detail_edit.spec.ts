import { expect, test, type Locator } from "@playwright/test"
import { loginUser, registerUser, uniqueName, uploadWithName } from "./utils"

// 统计画布上的非透明像素数：> 0 表示图片确实被绘制上去了
function countOpaquePixels(canvas: Locator): Promise<number> {
    return canvas.evaluate((el) => {
        const c = el as HTMLCanvasElement
        const ctx = c.getContext("2d")
        if (!ctx || !c.width || !c.height) return 0
        const { data } = ctx.getImageData(0, 0, c.width, c.height)
        let n = 0
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] > 0) n++
        }
        return n
    })
}

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

    // 回归防御：进入详情页后画布应「自动」显示图片。
    // 曾因 render() 在画布挂载前执行而空白，需用户点一次「旋转」触发 watch 才显示；
    // 因此这里必须在任何编辑操作之前断言，否则又会被后续操作掩盖。
    const preview = page.locator("canvas.preview-canvas")
    await expect(preview).toBeVisible()
    await expect
        .poll(() => countOpaquePixels(preview), { message: "详情页画布应自动绘制出图片（无需任何编辑操作）" })
        .toBeGreaterThan(0)

    // 旋转 → 保存 → 另存为新图
    await page.getByRole("button", { name: "旋转 90°" }).click()
    await page.getByRole("button", { name: "保存修改" }).click()
    await page.getByRole("button", { name: "另存为新图" }).click()

    // 跳回图库，应多一张「原名(编辑)」
    await page.waitForURL("**/gallery")
    await expect(page.locator(".image-grid").getByText(`${imgName}(编辑)`)).toBeVisible()
})
