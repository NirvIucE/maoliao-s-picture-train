import api from "./client";

// interface 定义了每个接口的请求/响应结构，
// 和 pydantic.BaseModel 是同样的概念——前端也要"校验"数据结构。
export interface ImageItem {
    id: number
    filename: string
    original_name: string
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
    file_size: number
    width: number
    height: number
    image_url: string
    thumbnail_url: string
}

// 获取图片列表
export function getImages(skip = 0, limit = 20): Promise<ImageListResponse> {
    return api.get("/images", { params: { skip, limit}})
}

// 获取图片详情
export function getImageDetail(imageId: number): Promise<ImageItem> {
    return api.get(`/images/${imageId}`)
}

// 上传图片文件
export function uploadImage(file: File): Promise<ImageUploadRequest> {
    const formData = new FormData()
    formData.append("file", file)
    return api.post("/images/upload", formData, {
        headers: {
            "Content-Type": "multipart/form-data"
        }
    })
}

// URL上传
export function uploadImageByUrl(url: string): Promise<ImageUploadRequest> {
    return api.post("/images/upload-url", { url })
}

// 删除图片
export function deleteImage(imageId: number): Promise<{ message: string }> {
    return api.delete(`/images/${imageId}`)
}
