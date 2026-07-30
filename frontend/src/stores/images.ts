
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

    let lastSearch = ""
    let lastSkip = 0
    let lastLimit = 20

    async function fetchImages(skip = 0, limit = 20, search?: string){
        loading.value = true
        lastSearch = search || ""
        lastSkip = skip
        lastLimit = limit
        try{
            const res = await getImages(skip, limit, search)
            images.value = res.items
            total.value = res.total
        } finally {
            loading.value = false
        }
    }
    async function upload(file: File, customName?: string){
        await uploadImage(file, customName)
        await fetchImages(lastSkip, lastLimit, lastSearch || undefined)
    }
    async function uploadFromUrl(url: string, customName?: string){
        await uploadImageByUrl(url, customName)
        await fetchImages(lastSkip, lastLimit, lastSearch || undefined)
    }
    async function removeImage(imageId: number){
        await deleteImageApi(imageId)
        await fetchImages(lastSkip, lastLimit, lastSearch || undefined)
    }
    return { images, total, loading, fetchImages, upload, uploadFromUrl, removeImage }
})