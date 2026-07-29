<!-- 上传页 -->
<script setup lang="ts">
import { ref } from "vue"
import { useImageStore } from "@/stores/images"
import { useRouter } from "vue-router"

const imageStore = useImageStore()
const router = useRouter()

const urlInput = ref("")
const uploading = ref(false)
const errorMsg = ref("")
const successMsg = ref("")

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if(!file){
    return 
  }
  errorMsg.value = ""
  successMsg.value = ""
  uploading.value = true
  try {
    await imageStore.upload(file)
    successMsg.value = `"${file.name}"上传成功`
    target.value = ""
  } catch (err:any) {
    errorMsg.value = err.response?.data?.detail || "上传失败"
  } finally {
    uploading.value = false
  }
}

async function handleUrlUpload() {
  if (!urlInput.value.trim()) {
    return 
  }
  errorMsg.value = ""
  successMsg.value = ""
  uploading.value = true
  try {
    await imageStore.uploadFromUrl(urlInput.value.trim())
    successMsg.value = `"url上传成功！"`
    urlInput.value = ""
  } catch (err:any) {
    errorMsg.value = err.response?.data?.detail || "上传失败"
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="upload-page">
    <h2>上传图片</h2>

    <!-- 文件上传 -->
    <div class="section">
      <h3>选择文件上传</h3>
      <input
        type="file"
        accept="image/*"
        :disabled="uploading"
        @change="handleFileUpload"
      />
    </div>

    <!-- URL 上传 -->
    <div class="section">
      <h3>通过 URL 上传</h3>
      <div class="url-row">
        <input
          v-model="urlInput"
          type="text"
          placeholder="粘贴图片 URL..."
          :disabled="uploading"
        />
        <button :disabled="uploading || !urlInput.trim()" @click="handleUrlUpload">
          上传
        </button>
      </div>
    </div>

    <!-- 提示信息 -->
    <p v-if="uploading" class="status">上传中...</p>
    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-if="successMsg" class="success">{{ successMsg }}</p>

    <router-link to="/gallery">← 返回图库</router-link>
  </div>
</template>

<style scoped>
.upload-page { padding: 20px 0; max-width: 600px; }
.section { margin-bottom: 30px; }
.url-row { display: flex; gap: 10px; }
.url-row input { flex: 1; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; }
.url-row button { padding: 8px 20px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; }
.url-row button:disabled { background: #ccc; cursor: not-allowed; }
.status { color: #909399; }
.error { color: #f56c6c; }
.success { color: #67c23a; }
</style>