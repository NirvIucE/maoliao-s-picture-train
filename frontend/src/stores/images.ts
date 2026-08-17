/*
 * @Author: NirvIucE 1750682685@qq.com
 * @Date: 2026-07-28 20:17:55
 * @LastEditors: NirvIucE 1750682685@qq.com
 * @LastEditTime: 2026-08-15 19:45:09
 * @FilePath: \new-picture-train\frontend\src\stores\images.ts
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */

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