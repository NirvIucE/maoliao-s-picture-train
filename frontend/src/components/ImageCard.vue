
<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { deleteImage, downloadOriginalImage } from "@/api/images"
import { submitToPublic } from "@/api/public"
import type { ImageItem } from "@/api/images"

const props = defineProps<{ image: ImageItem }>()
const emit = defineEmits<{ deleted: [] }>()

const router = useRouter()
const showConfirm = ref(false)
const deleting = ref(false)
// 提交公共库反馈消息（替代 alert）
const submitMsg = ref("")
const submitError = ref(false)
// 提交公共库时可选携带标签
const showTagInput = ref(false)
const submitTags = ref("")

async function handleDelete() {
  deleting.value = true
  try {
    await deleteImage(props.image.id)
    emit("deleted")
  } finally {
    deleting.value = false
    showConfirm.value = false
  }
}

async function handleDownload() {
  await downloadOriginalImage(props.image.id, props.image.original_name)
}

async function handleSubmitPublic() {
  submitMsg.value = ""
  submitError.value = false
  try {
    const tags = submitTags.value
      .split(/[,，、\s]+/)
      .map((t) => t.trim().replace(/^#+/, ""))
      .filter(Boolean)
    await submitToPublic(props.image.id, tags)
    submitMsg.value = "已提交到公共图库，等待审核"
    showTagInput.value = false
    submitTags.value = ""
  } catch (error: any) {
    submitMsg.value = error.response?.data?.detail || "提交失败"
    submitError.value = true
  }
}

function goDetail() {
    router.push(`/detail/${props.image.id}`)
}
</script>

<template>
    <div class="card" @dblclick="goDetail">
        <div class="card-image">
            <img 
                :src="image.thumbnail_url || image.image_url || ''" 
                :alt="image.display_name"
                loading="lazy"
            />
        </div>
        <div class="card-info">
            <p class="name" :title="image.display_name">
                {{ image.display_name }}
            </p>
            <p class="size">
                {{ (image.file_size / 1024).toFixed(1) }} KB
            </p>
            <div class="actions" @dblclick.stop>
              <button class="btn-download" @click="handleDownload">
                下载原图
              </button>
              <button v-if="!showTagInput" class="btn-public" @click="showTagInput = true">
                提交公共库
              </button>
              <div v-else class="tag-submit">
                <input v-model="submitTags" placeholder="标签（可选），逗号分隔" @keyup.enter="handleSubmitPublic" />
                <button class="btn-public" @click="handleSubmitPublic">确认提交</button>
                <button class="btn-cancel" @click="showTagInput = false; submitTags = ''">取消</button>
              </div>
              <button v-if="!showConfirm" class="btn-delete" @click="showConfirm = true">删除</button>
              <div v-else class="confirm">
                <span>确认？</span>
                <button class="btn-yes" :disabled="deleting" @click="handleDelete">是</button>
                <button class="btn-no" @click="showConfirm = false">否</button>
              </div>
            </div>
            <p v-if="submitMsg" class="submit-msg" :class="{ error: submitError }">{{ submitMsg }}</p>
        </div>
    </div>
</template>

<style scoped>
.card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); }
.card-image {
  width: 100%;
  height: 200px;
  overflow: hidden;
  background: #f0f0f0;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card-info {
  padding: 12px;
}
.name {
  margin: 0 0 4px 0;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.size {
  margin: 0 0 8px 0;
  color: #909399;
  font-size: 13px;
}
.actions { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  flex-wrap: wrap; 
}
.btn-download {
  padding: 3px 10px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
  font-size: 13px;
}
.btn-public {
  padding: 3px 10px;
  background: #67c23a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-delete {
  padding: 4px 12px;
  border: 1px solid #f56c6c;
  color: #f56c6c;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
}
.btn-delete:hover {
  background: #fef0f0;
}
.confirm {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-yes { padding: 3px 10px; background: #f56c6c; color: white; border: none; border-radius: 4px; cursor: pointer; }
.btn-no  { padding: 3px 10px; background: #e4e7ed; border: none; border-radius: 4px; cursor: pointer; }
.submit-msg { margin: 8px 0 0; font-size: 12px; color: #67c23a; }
.submit-msg.error { color: #f56c6c; }
.tag-submit { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tag-submit input {
  width: 140px;
  padding: 3px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
}
.btn-cancel { padding: 3px 10px; background: #e4e7ed; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
</style>