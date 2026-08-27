import { expect, test } from "@playwright/test"
import { loginUser, registerUser, uniqueName, uploadWithName } from "./utils"

test("流程1：注册→登录→上传→图库可见", async ({ page }) => {
    const username = uniqueName("e2e1")
    const imgName = uniqueName("img1")

    await registerUser(page, username, "Pass1234!", `${username}@test.com`)
    await loginUser(page, username, "Pass1234!")

    // 上传自定义名图片
    await uploadWithName(page, imgName)

    // 图库应出现该图片
    await page.goto("/gallery")
    await expect(page.locator(".image-grid").getByText(imgName)).toBeVisible()
})
