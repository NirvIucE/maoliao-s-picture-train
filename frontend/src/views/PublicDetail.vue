<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getPublicDetail, deletePublicImage, setPublicVisibility, type PublicImageDetail } from "@/api/public"

const route = useRoute()
const router = useRouter()

const detail = ref<PublicImageDetail | null>(null)
const loading = ref(false)
const acting = ref(false)

const canOperate = computed(() => !!detail.value && (detail.value.is_owner || detail.value.is_admin))

async function load() {
  loading.value = true
  try {
    detail.value = await getPublicDetail(Number(route.params.id))
  } catch (error: any) {
    alert(error.response?.data?.detail || "加载失败")
  } finally {
    loading.value = false
  }
}

async function handleToggleVisibility() {
  if (!detail.value) return
  acting.value = true
  try {
    await setPublicVisibility(detail.value.id, !detail.value.is_visible)
    await load()
  } catch (error: any) {
    alert(error.response?.data?.detail || "操作失败")
  } finally {
    acting.value = false
  }
}

async function handleDelete() {
  if (!detail.value) return
  if (!confirm("确定从公共图库删除该图片吗？")) return
  acting.value = true
  try {
    await deletePublicImage(detail.value.id)
    alert("已删除")
    router.push("/public")
  } catch (error: any) {
    alert(error.response?.data?.detail || "删除失败")
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="public-detail">
    <p v-if="loading">加载中...</p>
    <template v-else-if="detail">
      <div class="image-wrap">
        <img :src="detail.image_url || ''" :alt="detail.display_name" />
      </div>
      <div class="info">
        <h2>{{ detail.display_name }}</h2>
        <p class="meta">
          上传者：{{ detail.username || "未知" }}
          <span class="dot">·</span>
          可见性：{{ detail.is_visible ? "普通用户可见" : "已隐藏" }}
        </p>
        <div v-if="canOperate" class="ops">
          <button class="btn-toggle" :disabled="acting" @click="handleToggleVisibility">
            {{ detail.is_visible ? "设为普通用户不可见" : "设为普通用户可见" }}
          </button>
          <button class="btn-delete" :disabled="acting" @click="handleDelete">
            从公共图库删除
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.public-detail { padding: 20px 0; }
.image-wrap {
  max-width: 800px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.image-wrap img {
  width: 100%;
  display: block;
}
.info { margin-top: 16px; }
.info h2 { margin: 0 0 8px 0; }
.meta { margin: 0 0 16px 0; color: #909399; }
.dot { margin: 0 8px; }
.ops { display: flex; gap: 12px; }
.btn-toggle {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-delete {
  padding: 8px 16px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-toggle:disabled, .btn-delete:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
