<!-- 图库页 -->
<script setup lang="ts">
import { onMounted } from 'vue';
import { useImageStore } from '@/stores/images';
import ImageCard from '@/components/ImageCard.vue';

const imageStore = useImageStore()

onMounted(() => {
  imageStore.fetchImages()
})
</script>

<template>
  <div class="gallery">
    <h2>我的图片</h2>
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
        @deleted="imageStore.fetchImages()"
      />
    </div>
    <p class="count">共显示 {{ imageStore.total }} 张图片</p>
  </div>
</template>

<style scoped>
.gallery { padding: 20px 0; }
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}
.count { color: #909399; margin-top: 20px; }
</style>