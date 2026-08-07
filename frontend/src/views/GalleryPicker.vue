<script setup lang="ts">
import { ref, watch } from "vue"
import { getImages, type ImageItem } from "@/api/images"

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  select: [image: ImageItem]
}>()

const images = ref<ImageItem[]>([])
const loading = ref(false)
const search = ref("")
const total = ref(0)
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 弹窗打开时加载图片
watch(
  () => props.visible,
  (val) => {
    if (val) {
      search.value = ""
      loadImages()
    }
  }
)

// 搜索防抖
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadImages(), 300)
}

async function loadImages(){
    loading.value = true
    try{
        const res = await getImages(0, 50, search.value || undefined)
        images.value = res.items
        total.value = res.total
    }catch{
        // 忽略
    }finally{
        loading.value = false
    }
}

function selectImage(image: ImageItem){
    emit("select", image)
}
</script>

<template>
    <div v-if="visible" class="picker-overlay" @click.self="emit('close')">
        <div class="picker-panel">
            <div class="picker-header">
                <h3>选择图片</h3>
                <button class="btn-close" @click="emit('close')">✕</button>
            </div>

            <div class="picker-search">
                <input
                    v-model="search"
                    type="text"
                    placeholder="搜索图片名称..."
                    @input="onSearchInput"
                />
            </div>

            <div class="picker-grid">
                <div v-if="loading" class="picker-loading">加载中...</div>
                <div v-else-if="images.length === 0" class="picker-empty">
                    暂无图片，请先上传
                </div>
                <div v-for="img in images"
                     :key="img.id"
                     class="picker-item"
                     @click="selectImage(img)"
                >
                    <img :src="img.thumbnail_url || img.image_url || ''"
                         :alt="img.display_name"
                         loading="lazy"
                    />
                    <span class="picker-name">{{ img.display_name }}</span>
                </div>
            </div>

            <div v-if="total > 50" class="picker-footer">
                仅显示最近 50 张（共 {{ total }} 张），可使用搜索缩小范围
            </div>
        </div>
    </div>
</template>

<style scoped>
.picker-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.picker-panel {
  background: white;
  border-radius: 12px;
  width: 680px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
}
.picker-header h3 {
  margin: 0;
  font-size: 16px;
}
.btn-close {
  border: none;
  background: none;
  font-size: 20px;
  color: #909399;
  cursor: pointer;
  padding: 0 4px;
}
.btn-close:hover {
  color: #f56c6c;
}
.picker-search {
  padding: 12px 20px;
}
.picker-search input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-sizing: border-box;
}
.picker-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.picker-loading,
.picker-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: #909399;
  padding: 40px 0;
}
.picker-item {
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.picker-item:hover {
  border-color: #409eff;
}
.picker-item img {
  width: 100%;
  height: 110px;
  object-fit: cover;
  display: block;
}
.picker-name {
  display: block;
  padding: 6px 8px;
  font-size: 12px;
  color: #606266;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picker-footer {
  padding: 10px 20px;
  font-size: 12px;
  color: #909399;
  text-align: center;
  border-top: 1px solid #e4e7ed;
}
</style>