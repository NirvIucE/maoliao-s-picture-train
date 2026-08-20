<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useAuthStore } from "@/stores/auth"
import { getMyPublicImages, deletePublicImage, type PublicImageItem } from "@/api/public"

const auth = useAuthStore()
const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const deleting = ref<Record<number, boolean>>({})

const statusText: Record<string, string> = {
  pending: "待审核",
  approved: "已公开",
  rejected: "已驳回",
}

function formatTime(iso: string): string {
  if (!iso) return ""
  return iso.replace("T", " ").slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    const res = await getMyPublicImages(0, 50)
    items.value = res.items
    total.value = res.total
  } catch (error: any) {
    alert(error.response?.data?.detail || "加载失败")
  } finally {
    loading.value = false
  }
}

async function handleDelete(item: PublicImageItem) {
  const action = item.status === "pending" ? "撤回" : "删除"
  if (!confirm(`确定${action}这条记录吗？`)) return
  deleting.value[item.id] = true
  try {
    await deletePublicImage(item.id)
    await load()
  } catch (error: any) {
    alert(error.response?.data?.detail || `${action}失败`)
  } finally {
    delete deleting.value[item.id]
  }
}

onMounted(load)
</script>

<template>
  <div class="profile">
    <h2>个人主页</h2>
    <p class="welcome">你好，{{ auth.user?.username }}</p>

    <h3>我的公共图库提交</h3>

    <p v-if="loading">加载中...</p>
    <p v-else-if="items.length === 0">还没有提交过图片到公共图库</p>
    <div v-else class="list">
      <div v-for="item in items" :key="item.id" class="item">
        <img
          :src="item.thumbnail_url || item.image_url || ''"
          :alt="item.display_name"
          class="thumb"
        />
        <div class="meta">
          <p class="name">{{ item.display_name }}</p>
          <p class="status">
            <span :class="'tag-' + item.status">{{ statusText[item.status] || item.status }}</span>
            <span class="time">{{ formatTime(item.created_at) }}</span>
          </p>
          <p v-if="item.review_comment" class="comment">意见：{{ item.review_comment }}</p>
        </div>
        <div class="ops">
          <button
            v-if="item.status === 'pending'"
            class="btn-withdraw"
            :disabled="deleting[item.id]"
            @click="handleDelete(item)"
          >
            撤回
          </button>
          <button
            v-else
            class="btn-delete"
            :disabled="deleting[item.id]"
            @click="handleDelete(item)"
          >
            删除
          </button>
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 条提交</p>
  </div>
</template>

<style scoped>
.profile { padding: 20px 0; }
.welcome { color: #909399; }
h3 { margin-top: 24px; }
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
.status { margin: 0; font-size: 13px; }
.time { margin-left: 8px; color: #c0c4cc; }
.comment { margin: 4px 0 0 0; color: #909399; font-size: 13px; }
.tag-pending { color: #e6a23c; }
.tag-approved { color: #67c23a; }
.tag-rejected { color: #f56c6c; }
.ops { display: flex; gap: 8px; }
.btn-withdraw {
  padding: 6px 16px;
  background: #e6a23c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-delete {
  padding: 6px 16px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-withdraw:disabled, .btn-delete:disabled { opacity: 0.5; cursor: not-allowed; }
.count { color: #909399; margin-top: 20px; }
</style>
