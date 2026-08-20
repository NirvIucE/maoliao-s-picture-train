<script setup lang="ts">
import { onMounted, ref } from "vue"
import { getPublicImages, type PublicImageItem } from "@/api/public"

const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await getPublicImages(0, 50)
    items.value = res.items
    total.value = res.total
  } catch (error: any) {
    alert(error.response?.data?.detail || "加载失败")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="public-gallery">
    <h2>公共图库</h2>

    <p v-if="loading">加载中...</p>
    <p v-else-if="items.length === 0">公共图库暂无图片</p>
    <div v-else class="grid">
      <div v-for="item in items" :key="item.id" class="card">
        <a :href="item.image_url || '#'" target="_blank" rel="noopener">
          <img
            :src="item.thumbnail_url || item.image_url || ''"
            :alt="item.display_name"
            loading="lazy"
          />
        </a>
        <div class="info">
          <p class="name" :title="item.display_name">{{ item.display_name }}</p>
          <p class="author">by {{ item.username || "未知" }}</p>
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 张图片</p>
  </div>
</template>

<style scoped>
.public-gallery { padding: 20px 0; }
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
</style>
