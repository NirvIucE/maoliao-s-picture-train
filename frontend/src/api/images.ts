
import api from "./client";

// interface 定义了每个接口的请求/响应结构，
// 和 pydantic.BaseModel 是同样的概念——前端也要"校验"数据结构。
export interface ImageItem {
    id: number
    filename: string
    original_name: string
    custom_name: string | null
    display_name: string 
    file_size: number
    mime_type: string
    width: number | null
    height: number | null
    created_at: string
    thumbnail_url: string | null
    image_url: string | null
}

export interface ImageListResponse {
    total: number
    items: ImageItem[]
}

export interface ImageUploadRequest {
    id: number
    original_name: string
    custom_name: string | null
    display_name: string
    file_size: number
    width: number
    height: number
    image_url: string
    thumbnail_url: string
}

// 获取图片列表
export function getImages(skip = 0, limit = 20, search?: string): Promise<ImageListResponse> {
    const params: Record<string, any> = { skip, limit }
    if(search) params.search = search
    return api.get("/images", { params: params })
}

// 获取图片详情
export function getImageDetail(imageId: number): Promise<ImageItem> {
    return api.get(`/images/${imageId}`)
}

// 上传图片文件
export function uploadImage(file: File, customName?: string): Promise<ImageUploadRequest> {
    const formData = new FormData()
    formData.append("file", file)
    if(customName) formData.append("custom_name", customName)
    return api.post("/images/upload", formData, {
        headers: {
            "Content-Type": "multipart/form-data"
        }
    })
}

// URL上传
export function uploadImageByUrl(url: string, customName?: string): Promise<ImageUploadRequest> {
    return api.post("/images/upload-url", { url, custom_name: customName || null })
}

// 删除图片
export function deleteImage(imageId: number): Promise<{ message: string }> {
    return api.delete(`/images/${imageId}`)
}

// 下载原图URL（直接打开即可触发浏览器下载）
export function getDownloadUrl(imageId: number): string {
    return `/api/images/${imageId}/download`
}

// 下载原图（Axios携带Token，以blob方式接收）
export async function downloadOriginalImage(imageId: number, filename: string): Promise<void> {
    const response = await api.get(`/images/${imageId}/download`, { responseType: "blob", } as any)
    //创建临时URL触发浏览器下载
    const url = window.URL.createObjectURL(new Blob ([response as any]))
    const link = document.createElement("a")
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
}

// 编辑操作类型
export interface EditOperation {
    type: "rotate" | "flip" | "crop"
    angle?: number          // rotate: 90/180/270
    direction?: string      // flip: "horizontal"/"vertical"
    left?: number           // crop
    top?: number
    right?: number
    bottom?: number
}

// 编辑图片（裁剪/旋转/翻转）
export function editImage(
    imageId: number,
    operations: EditOperation[],
    saveMode: "overwrite" | "new",
    customName?: string
): Promise<ImageUploadRequest> {
    return api.post(`/images/${imageId}/edit`, {
        operations,
        save_mode: saveMode,
        custom_name: customName || null
    })
}

// 替换图片（覆盖原图，用于 AI 抠图结果）
export function replaceImage(imageId: number, file: Blob): Promise<ImageUploadRequest> {
    const formData = new FormData()
    // Blob 直接 append 会丢失文件名（后端拿到 "blob"），无法识别扩展名
    const namedFile = new File([file], "result.png", { type: file.type || "image/png" })
    formData.append("file", namedFile)
    return api.post(`/images/${imageId}/replace`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
    })
}

// AI 区域编辑（涂鸦 + 指令），返回结果图 base64, colorName 用于后端拼接 prompt
export function aiEditImage(
    imageId: number,
    prompt: string,
    imageBase64: string,
    colorName = "红色"
): Promise<{image_base64: string}> {
    return api.post(`/images/${imageId}/ai-edit`, { prompt, image_base64: imageBase64, color_name: colorName }, {timeout: 300000})
}
