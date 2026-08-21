
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
    is_visible: boolean
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

// 删除公共库记录（上传者本人或管理员）
export function deletePublicImage(publicId: number): Promise<{ message: string }> {
    return api.delete(`/public/images/${publicId}`)
}

// 公共图库详情（含当前用户权限判断）
export interface PublicImageDetail extends PublicImageItem {
    is_owner: boolean
    is_admin: boolean
}

export function getPublicDetail(publicId: number): Promise<PublicImageDetail> {
    return api.get(`/public/images/${publicId}`)
}

// 切换可见性
export function setPublicVisibility(publicId: number, visible: boolean): Promise<{ message: string }> {
    return api.post(`/public/images/${publicId}/visibility`, { visible })
}
