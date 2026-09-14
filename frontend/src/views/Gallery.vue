

<!-- 图库页 -->
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useImageStore } from '@/stores/images';
import { getImageTags, type ImageTagStat } from '@/api/images';
import ImageCard from '@/components/ImageCard.vue';


const imageStore = useImageStore()
const searchInput = ref("")
// 阶段 21：单选标签筛选，与搜索框同时生效时后端取 AND
const activeTag = ref("")
const tagStats = ref<ImageTagStat[]>([])

let searchTimer: ReturnType<typeof setTimeout> | null = null

function fetchPage(){
  return imageStore.fetchImages(
    0, 20, searchInput.value || undefined, activeTag.value || undefined
  )
}

function onSearch(){
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(fetchPage, 500);
}

// 点标签 chip：已选中则取消筛选
function toggleTag(tag: string){
  activeTag.value = activeTag.value === tag ? "" : tag
  fetchPage()
}

function clearFilters(){
  searchInput.value = ""
  activeTag.value = ""
  fetchPage()
}

async function loadTagStats(){
  try {
    const res = await getImageTags()
    tagStats.value = res.items
  } catch {
    // 筛选条是可选项，拉取失败不影响图库浏览
    tagStats.value = []
  }
}

async function onDeleted(){
  await fetchPage()
  await loadTagStats()  // 删除会改变各标签的使用次数
}

onMounted(() => {
  fetchPage()
  loadTagStats()
})
</script>

<template>
  <div class="gallery">
    <h2>我的图片</h2>

    <div class="search-bar">
      <input
        v-model="searchInput"
        type="text"
        placeholder="搜索图片名称..."
        @input="onSearch"
      />
    </div>

    <div v-if="tagStats.length" class="tag-filter-bar">
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

    <p v-if="imageStore.loading">加载中...</p>
    <p v-else-if="imageStore.error" class="error">{{ imageStore.error }}</p>
    <p v-else-if="imageStore.images.length === 0 && (activeTag || searchInput)">
      没有符合条件的图片，
      <button class="link-btn" @click="clearFilters">清除筛选</button>
    </p>
    <p v-else-if="imageStore.images.length === 0">暂无图片，去
      <router-link to="/upload">上传</router-link>
      一张吧！
    </p>
    <div v-else class="image-grid">
      <ImageCard 
        v-for="image in imageStore.images" 
        :key="image.id" 
        :image="image"
        @deleted="onDeleted"
        @filter-tag="toggleTag"
      />
    </div>
    <p class="count">共显示 {{ imageStore.total }} 张图片</p>
    <button
      v-if="imageStore.images.length < imageStore.total"
      class="load-more"
      :disabled="imageStore.loading"
      @click="imageStore.fetchMore()"
    >
      {{ imageStore.loading ? '加载中...' : '加载更多' }}
    </button>
    <p v-else-if="imageStore.images.length > 0" class="no-more">没有更多了</p>
    
  </div>
</template>

<style scoped>
.gallery { padding: 20px 0; }
.error { color: #f56c6c; }
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
.search-bar { margin-bottom: 20px; }
.search-bar input {
  width: 100%;
  max-width: 400px;
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
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
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}
.count { color: #909399; margin-top: 20px; }
</style>
