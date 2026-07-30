<!-- 上传页 -->
<script setup lang="ts">
import { ref } from "vue"
import { useImageStore } from "@/stores/images"

const imageStore = useImageStore()

const urlInput = ref("")
const customName = ref("")
const fileInput = ref<HTMLInputElement | null>(null) 
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const errorMsg = ref("")
const successMsg = ref("")

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] || null
}

async function handleFileUpload() {
  if(!selectedFile.value){
    return
  }
  errorMsg.value = ""
  successMsg.value = ""
  uploading.value = true
  try {
    await imageStore.upload(selectedFile.value, customName.value || undefined)
    successMsg.value = `"${customName.value || selectedFile.value.name}"上传成功`
    selectedFile.value = null
    customName.value = ""
    // 上传成功后清空file Input
    if(fileInput.value){
      fileInput.value.value = ""
    }
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
    await imageStore.uploadFromUrl(urlInput.value.trim(), customName.value || undefined)
    successMsg.value = `"url上传成功！"`
    urlInput.value = ""
    customName.value = ""
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

    <!-- 自定义名称 -->
    <div class="section">
      <h3>自定义名称（可选）</h3>
      <input
        v-model="customName"
        type="text"
        placeholder="可选，自定义图片名称"
        :disabled="uploading"
        class="name-input" 
      />
    </div>

    <!-- 文件上传 -->
    <div class="section">
      <h3>选择文件上传</h3>
      <div class="file-row">
        <input
        type="file"
        accept="image/*"
        :disabled="uploading"
        ref="fileInput"
        @change="onFileSelected"
        />
      <button :disabled="uploading || !selectedFile" @click="handleFileUpload">
          {{ uploading ? '上传中...' : '上传' }}
      </button>
      </div>
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
.name-input { width: 100%; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.url-row { display: flex; gap: 10px; }
.url-row input { flex: 1; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; }
.url-row button { padding: 8px 20px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; }
.url-row button:disabled { background: #ccc; cursor: not-allowed; }
.file-row { display: flex; gap: 10px; }
.file-row input { flex: 1; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; }
.file-row button { padding: 8px 20px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; }
.file-row button:disabled { background: #ccc; cursor: not-allowed; }
.status { color: #909399; }
.error { color: #f56c6c; }
.success { color: #67c23a; }
</style>