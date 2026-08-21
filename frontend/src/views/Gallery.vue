

<!-- 图库页 -->
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useImageStore } from '@/stores/images';
import ImageCard from '@/components/ImageCard.vue';


const imageStore = useImageStore()
const searchInput = ref("")

let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch(){
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    imageStore.fetchImages(0, 20, searchInput.value || undefined)
  }, 500);
}

onMounted(() => {
  imageStore.fetchImages()
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

    <p v-if="imageStore.loading">加载中...</p>
    <p v-else-if="imageStore.images.length === 0">暂无图片，去
      <router-link to="/upload">上传</router-link>
      一张吧！
    </p>
    <div v-else class="image-grid">
      <ImageCard 
        v-for="image in imageStore.images" 
        :key="image.id" 
        :image="image"
        @deleted="imageStore.fetchImages(0,20, searchInput || undefined)"
      />
    </div>
    <p class="count">共显示 {{ imageStore.total }} 张图片</p>
    
  </div>
</template>

<style scoped>
.gallery { padding: 20px 0; }
.search-bar { margin-bottom: 20px; }
.search-bar input {
  width: 100%;
  max-width: 400px;
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}
.count { color: #909399; margin-top: 20px; }
</style>