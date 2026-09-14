import { defineStore } from "pinia"
import { ref } from "vue"
import {
    getImages,
    uploadImage,
    uploadImageByUrl,
    deleteImage as deleteImageApi,
    type ImageItem,
} from "@/api/images"

export const useImageStore = defineStore("images", () => {
    const images = ref<ImageItem[]>([])
    const total = ref(0)
    const loading = ref(false)
    const error = ref("")

    let lastSearch = ""
    let lastTag = ""
    let lastSkip = 0
    let lastLimit = 20

    async function fetchImages(skip = 0, limit = 20, search?: string, tag?: string){
        loading.value = true
        error.value = ""
        lastSearch = search || ""
        lastTag = tag || ""
        lastSkip = skip
        lastLimit = limit
        try{
            const res = await getImages(skip, limit, search, tag)
            images.value = res.items
            total.value = res.total
        } catch (err: any) {
            error.value = err.response?.data?.detail || "加载失败"
        } finally {
            loading.value = false
        }
    }

    // 刷新当前页：保留搜索词与标签筛选（阶段 21）
    function reload(){
        return fetchImages(lastSkip, lastLimit, lastSearch || undefined, lastTag || undefined)
    }

    async function fetchMore(){
        if (images.value.length >= total.value) return
        loading.value = true
        error.value = ""
        try {
            const res = await getImages(
                images.value.length, lastLimit, lastSearch || undefined, lastTag || undefined
            )
            images.value.push(...res.items)
            total.value = res.total
        } catch (err: any) {
            error.value = err.response?.data?.detail || "加载失败"
        } finally {
            loading.value = false
        }
    }
    async function upload(file: File, customName?: string){
        await uploadImage(file, customName)
        await reload()
    }
    async function uploadFromUrl(url: string, customName?: string){
        await uploadImageByUrl(url, customName)
        await reload()
    }
    async function removeImage(imageId: number){
        await deleteImageApi(imageId)
        await reload()
    }
    return { images, total, loading, error, fetchImages, fetchMore, reload, upload, uploadFromUrl, removeImage }
})