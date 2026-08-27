<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { getPublicImages, type PublicImageItem } from "@/api/public"

const router = useRouter()
const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const errorMsg = ref("")
const hasMore = ref(false)
const searchInput = ref("")

let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    load(searchInput.value || undefined)
  }, 500)
}

async function load(search?: string) {
  loading.value = true
  errorMsg.value = ""
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

async function loadMore() {
  loading.value = true
  errorMsg.value = ""
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
        placeholder="搜索图片名称..."
        @input="onSearch"
      />
    </div>

    <p v-if="loading">加载中...</p>
    <p v-else-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-else-if="items.length === 0">公共图库暂无图片</p>
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
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 张图片</p>
    <button v-if="hasMore" class="load-more" :disabled="loading" @click="loadMore">
      {{ loading ? "加载中..." : "加载更多" }}
    </button>
    <p v-else-if="items.length > 0" class="no-more">没有更多了</p>
  </div>
</template>

<style scoped>
.public-gallery { padding: 20px 0; }
.error { color: #f56c6c; }
.search-bar { margin-bottom: 20px; }
.search-bar input {
  width: 100%;
  max-width: 400px;
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
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
