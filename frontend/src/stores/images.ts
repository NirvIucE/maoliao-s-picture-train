
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

    async function fetchImages(skip = 0, limit = 20){
        loading.value = true
        try{
            const res = await getImages(skip, limit)
            images.value = res.items
            total.value = res.total
        } finally {
            loading.value = false
        }
    }
    async function upload(file: File){
        await uploadImage(file)
        await fetchImages()
    }
    async function uploadFromUrl(url: string){
        await uploadImageByUrl(url)
        await fetchImages()
    }
    async function removeImage(imageId: number){
        await deleteImageApi(imageId)
        await fetchImages()
    }
    return { images, total, loading, fetchImages, upload, uploadFromUrl, removeImage }
})