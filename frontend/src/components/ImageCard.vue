
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
const tagInput = ref("")
const pendingTags = ref<string[]>([])

// 输入时即时剥离前导 #（##猫 → 猫）
function onTagInput() {
    tagInput.value = tagInput.value.replace(/^#+/, "")
}

// 逐个添加标签：清洗 + 去重后生成独立 chip
function addPendingTag() {
    const tag = tagInput.value.trim().replace(/^#+/, "")
    if (!tag) return
    if (!pendingTags.value.includes(tag)) {
        pendingTags.value.push(tag)
    }
    tagInput.value = ""
}

function removePendingTag(tag: string) {
    pendingTags.value = pendingTags.value.filter((t) => t !== tag)
}

function cancelSubmit() {
    showTagInput.value = false
    tagInput.value = ""
    pendingTags.value = []
}

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
    await submitToPublic(props.image.id, pendingTags.value)
    submitMsg.value = "已提交到公共图库，等待审核"
    cancelSubmit()
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
                <input v-model="tagInput" placeholder="标签（可选），回车添加" @input="onTagInput" @keyup.enter="addPendingTag" />
                <button class="btn-tag-add" :disabled="!tagInput.trim()" title="添加标签" @click="addPendingTag">+</button>
                <div v-if="pendingTags.length" class="pending-tags">
                  <span v-for="t in pendingTags" :key="t" class="tag-chip">
                    #{{ t }}
                    <button class="tag-remove" title="移除标签" @click="removePendingTag(t)">×</button>
                  </span>
                </div>
                <button class="btn-public" @click="handleSubmitPublic">确认提交</button>
                <button class="btn-cancel" @click="cancelSubmit">取消</button>
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
  width: 130px;
  padding: 3px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
}
.btn-tag-add {
  padding: 3px 10px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-tag-add:disabled { opacity: 0.5; cursor: not-allowed; }
.pending-tags { display: flex; flex-wrap: wrap; gap: 4px; width: 100%; }
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}
.tag-remove { border: none; background: none; color: #909399; cursor: pointer; font-size: 13px; line-height: 1; padding: 0 2px; }
.tag-remove:hover { color: #f56c6c; }
.btn-cancel { padding: 3px 10px; background: #e4e7ed; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
</style>