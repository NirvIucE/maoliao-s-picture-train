<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getPublicDetail, deletePublicImage, setPublicVisibility, downloadPublicImage, addTags, removeTag, type PublicImageDetail } from "@/api/public"
import { useAuthStore } from "@/stores/auth"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const detail = ref<PublicImageDetail | null>(null)
const loading = ref(false)
const acting = ref(false)
const downloading = ref(false)
// 标签输入与操作状态
const tagInput = ref("")
const tagActing = ref(false)
// 内联消息（与 C1/C2 阶段风格一致，替代 alert）
const successMsg = ref("")
const errorMsg = ref("")

const canOperate = computed(() => !!detail.value && (detail.value.is_owner || detail.value.is_admin))

// 单标签清洗：去首尾空白、剥掉所有前导 #、去空
function cleanTag(raw: string): string {
    return raw.trim().replace(/^#+/, "")
}

// 输入时即时剥离前导 #（多个 # 也无妨：##猫 → 猫）
function onTagInput() {
    tagInput.value = tagInput.value.replace(/^#+/, "")
}

async function handleAddTag() {
    if (!detail.value) return
    const tag = cleanTag(tagInput.value)
    if (!tag) return
    tagActing.value = true
    successMsg.value = ""
    errorMsg.value = ""
    try {
        if (detail.value.tags.includes(tag)) {
            errorMsg.value = `标签"${tag}"已存在`
            return
        }
        const res = await addTags(detail.value.id, [tag])
        tagInput.value = ""
        detail.value.tags = res.tags
        successMsg.value = `已添加标签 #${tag}`
    } catch (error: any) {
        errorMsg.value = error.response?.data?.detail || "添加标签失败"
    } finally {
        tagActing.value = false
    }
}

async function handleRemoveTag(tagName: string) {
    if (!detail.value) return
    tagActing.value = true
    successMsg.value = ""
    errorMsg.value = ""
    try {
        await removeTag(detail.value.id, tagName)
        detail.value.tags = detail.value.tags.filter((t) => t !== tagName)
        successMsg.value = "标签已删除"
    } catch (error: any) {
        errorMsg.value = error.response?.data?.detail || "删除标签失败"
    } finally {
        tagActing.value = false
    }
}

async function load() {
  loading.value = true
  successMsg.value = ""
  errorMsg.value = ""
  try {
    detail.value = await getPublicDetail(Number(route.params.id))
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "加载失败"
  } finally {
    loading.value = false
  }
}

async function handleToggleVisibility() {
  if (!detail.value) return
  acting.value = true
  successMsg.value = ""
  errorMsg.value = ""
  try {
    await setPublicVisibility(detail.value.id, !detail.value.is_visible)
    await load()
    // 在 load 清空消息之后设置成功提示（is_visible 已是切换后的新值）
    successMsg.value = detail.value.is_visible ? "已设为普通用户可见" : "已设为普通用户不可见"
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "操作失败"
  } finally {
    acting.value = false
  }
}

async function handleDelete() {
  if (!detail.value) return
  if (!confirm("确定从公共图库删除该图片吗？")) return
  acting.value = true
  successMsg.value = ""
  errorMsg.value = ""
  try {
    await deletePublicImage(detail.value.id)
    successMsg.value = "已删除"
    router.push("/public")
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "删除失败"
  } finally {
    acting.value = false
  }
}

async function handleDownload() {
  if (!detail.value || !auth.isLoggedIn) return
  downloading.value = true
  successMsg.value = ""
  errorMsg.value = ""
  try {
    await downloadPublicImage(detail.value.id, detail.value.display_name, detail.value.image_url || "")
  } catch (error: any) {
    errorMsg.value = error.response?.data?.detail || "下载失败"
  } finally {
    downloading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="public-detail">
    <p v-if="successMsg" class="success-msg">{{ successMsg }}</p>
    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
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
        <div class="tags-section">
          <div v-if="detail.tags.length" class="tag-list">
            <span v-for="tag in detail.tags" :key="tag" class="tag-chip">
              #{{ tag }}
              <button v-if="canOperate" class="tag-remove" :disabled="tagActing" title="删除标签" @click="handleRemoveTag(tag)">×</button>
            </span>
          </div>
          <div v-else class="tag-empty">暂无标签</div>
          <div v-if="canOperate" class="tag-add">
            <input v-model="tagInput" placeholder="输入标签后回车添加，无需 # 前缀" @input="onTagInput" @keyup.enter="handleAddTag" />
            <button class="btn-tag-add" :disabled="tagActing || !tagInput.trim()" @click="handleAddTag">
              {{ tagActing ? "添加中..." : "添加" }}
            </button>
          </div>
        </div>
        <div class="download-section">
          <button v-if="auth.isLoggedIn" class="btn-download" :disabled="downloading" @click="handleDownload">
            {{ downloading ? "下载中..." : "下载图片" }}
          </button>
          <div v-else class="download-locked">
            <button class="btn-download" disabled>下载图片</button>
            <span class="hint">登陆后可下载图片</span>
          </div>
        </div>
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
.success-msg { color: #67c23a; margin-bottom: 12px; }
.error-msg { color: #f56c6c; margin-bottom: 12px; }
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
.download-section { margin: 16px 0; }
.btn-download {
  padding: 8px 16px;
  background: #67c23a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-download:disabled { opacity: 0.5; cursor: not-allowed; }
.download-locked { display: flex; align-items: center; gap: 12px; }
.download-locked .hint { color: #e6a23c; font-size: 14px; }
.tags-section { margin: 16px 0; }
.tag-list { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 13px;
}
.tag-remove { border: none; background: none; color: #909399; cursor: pointer; font-size: 14px; line-height: 1; padding: 0 2px; }
.tag-remove:hover { color: #f56c6c; }
.tag-remove:disabled { cursor: not-allowed; }
.tag-empty { color: #c0c4cc; font-size: 13px; margin-bottom: 12px; }
.tag-add { display: flex; gap: 8px; }
.tag-add input { flex: 1; padding: 6px 10px; border: 1px solid #dcdfe6; border-radius: 4px; }
.btn-tag-add { padding: 6px 14px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; }
.btn-tag-add:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
