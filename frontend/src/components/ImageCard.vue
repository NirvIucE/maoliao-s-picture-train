
<script setup lang="ts">
import { ref } from "vue"
import { deleteImage } from "@/api/images"
import type { ImageItem } from "@/api/images"

const props = defineProps<{ image: ImageItem }>()
const emit = defineEmits<{ deleted: [] }>()

const showConfirm = ref(false)
const deleting = ref(false)

async function handleDelete() {
  deleting.value = true
  try {
    await deleteImage(props.image.id)
    emit("deleted")
  } finally {
    deleting.value = false
    showConfirm.value = false
  }
}
</script>

<template>
    <div class="card">
        <div class="card-image">
            <img 
                :src="image.thumbnail_url || image.image_url || ''" 
                :alt="image.original_name"
                loading="lazy"
            />
        </div>
        <div class="card-info">
            <p class="name" :title="image.original_name">
                {{ image.original_name }}
            </p>
            <p class="size">
                {{ (image.file_size / 1024).toFixed(1) }} KB
            </p>
            <button 
                v-if="!showConfirm"
                class="btn-delete"
                @click="showConfirm = true"
            >
                删除图片
            </button>
            <div v-else class="confirm">
                <span>
                    确认删除吗？
                </span>
                <button class="btn-yes" :disabled="deleting" @click="handleDelete">确认</button>
                <button class="btn-no" @click="showConfirm = false">取消</button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); }
.card-image {
  width: 100%;
  height: 200px;
  overflow: hidden;
  background: #f0f0f0;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card-info {
  padding: 12px;
}
.name {
  margin: 0 0 4px 0;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.size {
  margin: 0 0 8px 0;
  color: #909399;
  font-size: 13px;
}
.btn-delete {
  padding: 4px 12px;
  border: 1px solid #f56c6c;
  color: #f56c6c;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
}
.btn-delete:hover {
  background: #fef0f0;
}
.confirm {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-yes { padding: 3px 10px; background: #f56c6c; color: white; border: none; border-radius: 4px; cursor: pointer; }
.btn-no  { padding: 3px 10px; background: #e4e7ed; border: none; border-radius: 4px; cursor: pointer; }
</style>