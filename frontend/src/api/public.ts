import api from "./client"
import type { ImageTagStat } from "./images"

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
    tags: string[]
}

export interface PublicImageListResponse {
    total: number
    items: PublicImageItem[]
}

// 提交图片到公共图库（仅从自己图库选图，可选携带标签）
export function submitToPublic(imageId: number, tags: string[] = []): Promise<PublicImageItem> {
    return api.post("/public/images", { image_id: imageId, tags })
}

// 浏览公共图库（仅审核通过的图片，支持按名称搜索 + 标签筛选）
export function getPublicImages(skip = 0, limit = 20, search?: string, tag?: string): Promise<PublicImageListResponse> {
    const params: Record<string, any> = { skip, limit }
    if(search) params.search = search
    if(tag) params.tag = tag
    return api.get("/public/images", { params: params })
}

// 阶段 22：公共图库标签统计（筛选条数据源）
// 口径随当前请求者角色变化，匿名只统计可见图片 —— 由后端负责，前端不再自行聚合
export interface PublicTagListResponse {
    total: number
    items: ImageTagStat[]
}

export function getPublicTags(): Promise<PublicTagListResponse> {
    return api.get("/public/images/tags")
}

// AI 搜索公共图库（语义：标题+标签 / 识图：视觉模型），note 为后端附加提示
export interface AISearchResponse extends PublicImageListResponse {
    note: string | null
}

export function aiSearchPublic(query: string, mode: "semantic" | "vision"): Promise<AISearchResponse> {
    return api.post("/public/images/ai-search", { query, mode })
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

// 给公共图库图片添加标签（上传者本人或管理员）
export function addTags(publicId: number, tags: string[]): Promise<{ message: string; tags: string[] }> {
    return api.post(`/public/images/${publicId}/tags`, { tags })
}

// 从公共图库图片移除标签（上传者本人或管理员）
export function removeTag(publicId: number, tagName: string): Promise<{ message: string }> {
    return api.delete(`/public/images/${publicId}/tags/${encodeURIComponent(tagName)}`)
}

// 下载公共图库图片（需登录）
export async function downloadPublicImage(publicId: number, displayName: string, imageUrl: string): Promise<void> {
    const blob = await api.get<Blob>(`/public/images/${publicId}/download`, { responseType: "blob" })
    // 从 imageUrl 提取扩展名，拼到下载文件名后
    const ext = imageUrl.match(/\.(jpg|jpeg|png|gif|bmp|webp|tiff)$/i)?.[0] || ""
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = displayName + ext || "download" + ext
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}
