/*
 * @Author: NirvIucE 1750682685@qq.com
 * @Date: 2026-08-20 20:22:37
 * @LastEditors: NirvIucE 1750682685@qq.com
 * @LastEditTime: 2026-08-20 20:24:41
 * @FilePath: \new-picture-train\frontend\src\api\public.ts
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
import api from "./client"

export interface PublicImageItem {
    id: number
    image_id: number
    user_id: number
    username: string | null
    status: string
    review_comment: string | null
    reviewed_by: number | null
    reviewed_at: string | null
    created_at: string
    display_name: string
    thumbnail_url: string | null
    image_url: string | null
}

export interface PublicImageListResponse {
    total: number
    items: PublicImageItem[]
}

// 提交图片到公共图库（仅从自己图库选图）
export function submitToPublic(imageId: number): Promise<PublicImageItem> {
    return api.post("/public/images", { image_id: imageId })
}

// 浏览公共图库（仅审核通过的图片）
export function getPublicImages(skip = 0, limit = 20): Promise<PublicImageListResponse> {
    return api.get("/public/images", { params: { skip, limit } })
}

// 我的提交记录（含各状态）
export function getMyPublicImages(skip = 0, limit = 20): Promise<PublicImageListResponse> {
    return api.get("/public/images/my", { params: { skip, limit } })
}

// 待审核列表（管理员）
export function getPendingPublicImages(skip = 0, limit = 20): Promise<PublicImageListResponse> {
    return api.get("/public/images/pending", { params: { skip, limit } })
}

// 审核（通过/拒绝）
export function reviewPublicImage(publicId: number, action: "approve" | "reject", comment?: string): Promise<{ message: string }> {
    return api.post(`/public/images/${publicId}/review`, { action, comment: comment || null })
}

// 管理员下架
export function removePublicImage(publicId: number, comment?: string): Promise<{ message: string }> {
    return api.post(`/public/images/${publicId}/remove`, { comment: comment || null })
}

// 作者删除自己的公共库记录（撤回 pending / 主动删除 approved）
export function deletePublicImage(publicId: number): Promise<{ message: string }> {
    return api.delete(`/public/images/${publicId}`)
}
