<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { aiSearchPublic, getPublicImages, type PublicImageItem } from "@/api/public"

const router = useRouter()
const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const errorMsg = ref("")
const hasMore = ref(false)
const searchInput = ref("")
const aiEnabled = ref(false)
const aiMode = ref<"semantic" | "vision">("semantic")
const aiNote = ref("")

function onSearch() {
  if (aiEnabled.value) {
    if (!searchInput.value.trim()) {
      items.value = []
      total.value = 0
      hasMore.value = false
      errorMsg.value = ""
      aiNote.value = "输入搜索词后即可使用 AI 搜索"
    } else {
      aiLoad()
    }
  } else {
    load(searchInput.value || undefined)
  }
}

function onAiToggle() {
  // 仅切换 AI 开关/模式，不自动搜索；点击"搜索"按钮后执行
  aiNote.value = aiEnabled.value && !searchInput.value.trim() ? "输入搜索词后即可使用 AI 搜索" : ""
}

async function load(search?: string) {
  loading.value = true
  errorMsg.value = ""
  aiNote.value = ""
  try {
    const res = await getPublicImages(0, 50, search)
    items.value = res.items
    total.value = res.total
    hasMore.value = items.value.length < total.value
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "加载失败"
  } finally {
    loading.value = false
  }
}

async function aiLoad() {
  const query = searchInput.value.trim()
  loading.value = true
  errorMsg.value = ""
  aiNote.value = ""
  try {
    const res = await aiSearchPublic(query, aiMode.value)
    items.value = res.items
    total.value = res.total
    hasMore.value = false
    aiNote.value = res.note || ""
  } catch (error: any) {
    const status = error.response?.status
    const detail = error.response?.data?.detail || ""
    if (status === 503) {
      errorMsg.value = detail || "未配置 AI 模型，无法使用 AI 搜索，请关闭 AI 搜索开关后重试"
    } else if (status === 502) {
      errorMsg.value = detail || "AI 搜索失败，请稍后重试或关闭 AI 搜索开关"
    } else if (status === 400) {
      errorMsg.value = detail || "请输入搜索词"
    } else {
      errorMsg.value = detail || "AI 搜索失败"
    }
    items.value = []
    total.value = 0
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loading.value = true
  errorMsg.value = ""
  aiNote.value = ""
  try {
    const res = await getPublicImages(items.value.length, 50, searchInput.value || undefined)
    items.value.push(...res.items)
    hasMore.value = items.value.length < total.value
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "加载失败"
  } finally {
    loading.value = false
  }
}

function goDetail(id: number) {
  router.push(`/public/${id}`)
}

onMounted(() => load())
</script>

<template>
  <div class="public-gallery">
    <h2>公共图库</h2>

    <div class="search-bar">
      <input
        v-model="searchInput"
        type="text"
        placeholder="搜索图片名称 / #标签（如 #猫）"
      />
      <button class="search-btn" :disabled="loading" @click="onSearch">搜索</button>
      <label class="ai-switch">
        <input type="checkbox" v-model="aiEnabled" @change="onAiToggle" />
        <span class="ai-switch-text">AI 搜索</span>
      </label>
      <select v-if="aiEnabled" v-model="aiMode" class="ai-mode" @change="onAiToggle">
        <option value="semantic">语义匹配（标题+标签）</option>
        <option value="vision">识图匹配</option>
      </select>
    </div>

    <p v-if="loading">{{ aiEnabled ? "AI 搜索中..." : "加载中..." }}</p>
    <p v-else-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-else-if="aiNote" class="note">{{ aiNote }}</p>
    <p v-else-if="items.length === 0">{{ aiEnabled ? "没有找到匹配的图片" : "公共图库暂无图片" }}</p>
    <div v-else class="grid">
      <div v-for="item in items" :key="item.id" class="card" @dblclick="goDetail(item.id)">
        <img
          :src="item.thumbnail_url || item.image_url || ''"
          :alt="item.display_name"
          loading="lazy"
        />
        <div class="info">
          <p class="name" :title="item.display_name">{{ item.display_name }}</p>
          <p class="author">by {{ item.username || "未知" }}</p>
          <div v-if="item.tags?.length" class="tags">
            <span v-for="tag in item.tags.slice(0, 3)" :key="tag" class="tag-chip">#{{ tag }}</span>
            <span v-if="item.tags.length > 3" class="tag-more">+{{ item.tags.length - 3 }}</span>
          </div>
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 张图片</p>
    <button v-if="!aiEnabled && hasMore" class="load-more" :disabled="loading" @click="loadMore">
      {{ loading ? "加载中..." : "加载更多" }}
    </button>
    <p v-else-if="!aiEnabled && items.length > 0" class="no-more">没有更多了</p>
  </div>
</template>

<style scoped>
.public-gallery { padding: 20px 0; }
.error { color: #f56c6c; }
.note { color: #e6a23c; }
.search-bar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.search-bar input {
  width: 100%;
  max-width: 400px;
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
.search-btn {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.search-btn:disabled { background: #a0cfff; cursor: not-allowed; }
.ai-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  user-select: none;
}
.ai-mode {
  padding: 6px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 13px;
  color: #606266;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}
.card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); }
.card img {
  width: 100%;
  height: 200px;
  object-fit: cover;
  display: block;
}
.info { padding: 12px; }
.name {
  margin: 0 0 4px 0;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.author { margin: 0; color: #909399; font-size: 13px; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.tag-chip {
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}
.tag-more { color: #909399; font-size: 12px; line-height: 20px; }
.count { color: #909399; margin-top: 20px; }
.load-more {
  display: block;
  margin: 20px auto;
  padding: 8px 24px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.load-more:disabled { background: #a0cfff; cursor: not-allowed; }
.no-more { color: #c0c4cc; text-align: center; margin-top: 20px; }
</style>
