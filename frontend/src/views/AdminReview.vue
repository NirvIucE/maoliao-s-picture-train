<script setup lang="ts">
import { onMounted, ref } from "vue"
import { getPendingPublicImages, reviewPublicImage, type PublicImageItem } from "@/api/public"

const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const comments = ref<Record<number, string>>({})
const actionLoading = ref<Record<number, boolean>>({})
const successMsg = ref("")
const errorMsg = ref("")

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const res = await getPendingPublicImages(0, 50)
    items.value = res.items
    total.value = res.total
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "加载失败"
  } finally {
    loading.value = false
  }
}

async function handleReview(item: PublicImageItem, action: "approve" | "reject") {
  actionLoading.value[item.id] = true
  successMsg.value = ""
  errorMsg.value = ""
  try {
    await reviewPublicImage(item.id, action, comments.value[item.id] || undefined)
    successMsg.value = action === "approve" ? "已通过审核" : "已驳回"
    await load()
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "操作失败"
  } finally {
    delete actionLoading.value[item.id]
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-review">
    <h2>待审核图片</h2>

    <p v-if="successMsg" class="success">{{ successMsg }}</p>
    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-if="loading">加载中...</p>
    <p v-else-if="items.length === 0">暂无待审核图片</p>
    <div v-else class="list">
      <div v-for="item in items" :key="item.id" class="item">
        <img
          :src="item.thumbnail_url || item.image_url || ''"
          :alt="item.display_name"
          class="thumb"
        />
        <div class="meta">
          <p class="name">{{ item.display_name }}</p>
          <p class="author">提交者：{{ item.username || "未知" }}</p>
          <input
            v-model="comments[item.id]"
            type="text"
            placeholder="审核意见（可选）"
          />
        </div>
        <div class="ops">
          <button
            class="btn-approve"
            :disabled="actionLoading[item.id]"
            @click="handleReview(item, 'approve')"
          >
            通过
          </button>
          <button
            class="btn-reject"
            :disabled="actionLoading[item.id]"
            @click="handleReview(item, 'reject')"
          >
            拒绝
          </button>
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 条待审核</p>
  </div>
</template>

<style scoped>
.admin-review { padding: 20px 0; }
.success { color: #67c23a; margin-bottom: 12px; }
.error { color: #f56c6c; margin-bottom: 12px; }
.list { display: flex; flex-direction: column; gap: 16px; }
.item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}
.thumb { width: 120px; height: 90px; object-fit: cover; border-radius: 4px; }
.meta { flex: 1; }
.name { margin: 0 0 4px 0; font-weight: 500; }
.author { margin: 0 0 8px 0; color: #909399; font-size: 13px; }
.meta input { width: 100%; max-width: 300px; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }
.ops { display: flex; gap: 8px; }
.btn-approve { padding: 6px 16px; background: #67c23a; color: white; border: none; border-radius: 4px; cursor: pointer; }
.btn-reject { padding: 6px 16px; background: #f56c6c; color: white; border: none; border-radius: 4px; cursor: pointer; }
.btn-approve:disabled, .btn-reject:disabled { opacity: 0.5; cursor: not-allowed; }
.count { color: #909399; margin-top: 20px; }
</style>
