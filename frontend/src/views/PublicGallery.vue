<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import {
  aiSearchPublic,
  getPublicImages,
  getPublicTags,
  type ImageTagStat,
  type PublicImageItem,
} from "@/api/public"

const router = useRouter()
const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const errorMsg = ref("")
const hasMore = ref(false)
const searchInput = ref("")
const aiEnabled = ref(false)
const aiNote = ref("")
// 阶段 22：单选标签筛选，与搜索框同时生效时后端取 AND
const activeTag = ref("")
const tagStats = ref<ImageTagStat[]>([])

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
    load()
  }
}

function onAiToggle() {
  // 仅切换 AI 开关，不自动搜索；点击"搜索"按钮后执行
  aiNote.value = aiEnabled.value && !searchInput.value.trim() ? "输入搜索词后即可使用 AI 搜索" : ""
}

// 当前筛选条件（search + tag），列表请求统一从这里取，避免各处拼参数漏掉 tag
function currentSearch(): string | undefined {
  return searchInput.value || undefined
}

function currentTag(): string | undefined {
  return activeTag.value || undefined
}

async function load() {
  loading.value = true
  errorMsg.value = ""
  aiNote.value = ""
  try {
    const res = await getPublicImages(0, 50, currentSearch(), currentTag())
    items.value = res.items
    total.value = res.total
    hasMore.value = items.value.length < total.value
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "加载失败"
  } finally {
    loading.value = false
  }
}

// 阶段 22：点标签 chip 筛选；已选中再点一次取消
function toggleTag(tag: string) {
  if (aiEnabled.value) return
  activeTag.value = activeTag.value === tag ? "" : tag
  load()
}

function clearFilters() {
  searchInput.value = ""
  activeTag.value = ""
  load()
}

async function loadTagStats() {
  try {
    const res = await getPublicTags()
    tagStats.value = res.items
  } catch {
    // 筛选条是可选项：拉取失败不影响公共图库浏览
    tagStats.value = []
  }
}

async function aiLoad() {
  const query = searchInput.value.trim()
  loading.value = true
  errorMsg.value = ""
  aiNote.value = ""
  try {
    // 识图搜索需逐张上传 AI 判断、耗时过长易超时，暂从前端隐藏，仅保留语义匹配（后端 vision 通道保留，后续可恢复）
    const res = await aiSearchPublic(query, "semantic")
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
    const res = await getPublicImages(items.value.length, 50, currentSearch(), currentTag())
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

onMounted(() => {
  load()
  loadTagStats()
})
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
    </div>

    <!-- 阶段 22：标签筛选条。AI 搜索模式隐藏（AI 走另一套召回口径，混入标签筛选无法解释结果） -->
    <div v-if="!aiEnabled && tagStats.length" class="tag-filter-bar">
      <span class="filter-label">按标签筛选：</span>
      <button
        v-for="tag in tagStats"
        :key="tag.name"
        class="filter-chip"
        :class="{ active: activeTag === tag.name }"
        @click="toggleTag(tag.name)"
      >
        #{{ tag.name }}<span class="chip-count">{{ tag.count }}</span>
      </button>
      <button v-if="activeTag || searchInput" class="filter-clear" @click="clearFilters">
        清除筛选
      </button>
    </div>

    <p v-if="loading">{{ aiEnabled ? "AI 搜索中..." : "加载中..." }}</p>
    <p v-else-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-else-if="aiNote" class="note">{{ aiNote }}</p>
    <p v-else-if="items.length === 0 && !aiEnabled && (activeTag || searchInput)">
      没有符合条件的图片，
      <button class="link-btn" @click="clearFilters">清除筛选</button>
    </p>
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
          <div v-if="item.tags?.length" class="tags" @dblclick.stop>
            <button
              v-for="tag in item.tags.slice(0, 3)"
              :key="tag"
              class="tag-chip"
              :class="{ active: activeTag === tag }"
              :title="`筛选标签 #${tag}`"
              @click.stop="toggleTag(tag)"
            >#{{ tag }}</button>
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
/* 阶段 22：标签筛选条（与个人图库保持一致的视觉） */
.tag-filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}
.filter-label { color: #909399; font-size: 13px; }
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 12px;
  font-size: 13px;
  cursor: pointer;
}
.filter-chip.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}
.chip-count {
  font-size: 11px;
  opacity: 0.75;
}
.filter-clear {
  padding: 3px 10px;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
  border-radius: 12px;
  font-size: 13px;
  cursor: pointer;
}
.link-btn {
  border: none;
  background: none;
  color: #409eff;
  cursor: pointer;
  font-size: inherit;
  padding: 0;
  text-decoration: underline;
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
/* 阶段 22：卡片标签由 span 改为 button（可点击筛选） */
.tag-chip {
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}
.tag-chip:hover { background: #d9ecff; }
.tag-chip.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
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
