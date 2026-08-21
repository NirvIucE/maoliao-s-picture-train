<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useAuthStore } from "@/stores/auth"
import { getMyPublicImages, deletePublicImage, type PublicImageItem } from "@/api/public"
import { updateUsername, changePassword, uploadAvatar } from "@/api/auth"

const auth = useAuthStore()
const items = ref<PublicImageItem[]>([])
const loading = ref(false)
const total = ref(0)
const deleting = ref<Record<number, boolean>>({})

// 资料编辑
const usernameInput = ref("")
const oldPassword = ref("")
const newPassword = ref("")
const confirmPassword = ref("")
const saving = ref(false)
const avatarFile = ref<File | null>(null)

const statusText: Record<string, string> = {
  pending: "待审核",
  approved: "已公开",
  rejected: "已驳回",
}

function formatTime(iso: string): string {
  if (!iso) return ""
  return iso.replace("T", " ").slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    const res = await getMyPublicImages(0, 50)
    items.value = res.items
    total.value = res.total
  } catch (error: any) {
    alert(error.response?.data?.detail || "加载失败")
  } finally {
    loading.value = false
  }
}

async function handleDelete(item: PublicImageItem) {
  const action = item.status === "pending" ? "撤回" : "删除"
  if (!confirm(`确定${action}这条记录吗？`)) return
  deleting.value[item.id] = true
  try {
    await deletePublicImage(item.id)
    await load()
  } catch (error: any) {
    alert(error.response?.data?.detail || `${action}失败`)
  } finally {
    delete deleting.value[item.id]
  }
}

function onAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  avatarFile.value = input.files?.[0] || null
}

async function handleUploadAvatar() {
  if (!avatarFile.value) {
    alert("请先选择图片")
    return
  }
  saving.value = true
  try {
    await uploadAvatar(avatarFile.value)
    await auth.fetchUser()
    avatarFile.value = null
    alert("头像已更新")
  } catch (error: any) {
    alert(error.response?.data?.detail || "上传失败")
  } finally {
    saving.value = false
  }
}

async function handleUpdateUsername() {
  const name = usernameInput.value.trim()
  if (!name) {
    alert("请输入新用户名")
    return
  }
  saving.value = true
  try {
    await updateUsername(name)
    await auth.fetchUser()
    usernameInput.value = ""
    alert("用户名已更新")
  } catch (error: any) {
    alert(error.response?.data?.detail || "更新失败")
  } finally {
    saving.value = false
  }
}

async function handleChangePassword() {
  if (newPassword.value !== confirmPassword.value) {
    alert("两次输入的新密码不一致")
    return
  }
  saving.value = true
  try {
    await changePassword(oldPassword.value, newPassword.value)
    oldPassword.value = ""
    newPassword.value = ""
    confirmPassword.value = ""
    alert("密码已更新")
  } catch (error: any) {
    alert(error.response?.data?.detail || "修改失败")
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="profile">
    <h2>个人主页</h2>
    <p class="welcome">你好，{{ auth.user?.username }}</p>
    <p v-if="auth.user?.uid" class="uid">专属 UID：{{ auth.user.uid }}</p>

    <div class="edit-panel">
      <h3>资料编辑</h3>

      <div class="edit-row">
        <span class="label">头像</span>
        <div class="avatar-box">
          <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="avatar" alt="头像" />
          <div v-else class="avatar placeholder">无</div>
        </div>
        <input type="file" accept="image/*" @change="onAvatarChange" />
        <button class="btn-primary" :disabled="saving || !avatarFile" @click="handleUploadAvatar">
          上传头像
        </button>
      </div>

      <div class="edit-row">
        <span class="label">用户名</span>
        <input
          v-model="usernameInput"
          type="text"
          :placeholder="`当前：${auth.user?.username}`"
          class="input"
        />
        <button class="btn-primary" :disabled="saving" @click="handleUpdateUsername">
          保存用户名
        </button>
      </div>

      <div class="edit-row">
        <span class="label">修改密码</span>
        <div class="pwd-group">
          <input v-model="oldPassword" type="password" placeholder="旧密码" class="input" />
          <input v-model="newPassword" type="password" placeholder="新密码（至少 6 位）" class="input" />
          <input v-model="confirmPassword" type="password" placeholder="确认新密码" class="input" />
          <button class="btn-primary" :disabled="saving" @click="handleChangePassword">
            修改密码
          </button>
        </div>
      </div>
    </div>

    <h3>我的公共图库提交</h3>

    <p v-if="loading">加载中...</p>
    <p v-else-if="items.length === 0">还没有提交过图片到公共图库</p>
    <div v-else class="list">
      <div v-for="item in items" :key="item.id" class="item">
        <img
          :src="item.thumbnail_url || item.image_url || ''"
          :alt="item.display_name"
          class="thumb"
        />
        <div class="meta">
          <p class="name">{{ item.display_name }}</p>
          <p class="status">
            <span :class="'tag-' + item.status">{{ statusText[item.status] || item.status }}</span>
            <span class="time">{{ formatTime(item.created_at) }}</span>
          </p>
          <p v-if="item.review_comment" class="comment">意见：{{ item.review_comment }}</p>
        </div>
        <div class="ops">
          <button
            v-if="item.status === 'pending'"
            class="btn-withdraw"
            :disabled="deleting[item.id]"
            @click="handleDelete(item)"
          >
            撤回
          </button>
          <button
            v-else
            class="btn-delete"
            :disabled="deleting[item.id]"
            @click="handleDelete(item)"
          >
            删除
          </button>
        </div>
      </div>
    </div>
    <p class="count">共 {{ total }} 条提交</p>
  </div>
</template>

<style scoped>
.profile { padding: 20px 0; }
.welcome { color: #909399; }
.uid { color: #909399; font-size: 13px; }
h3 { margin-top: 24px; }
.edit-panel {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}
.edit-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.label { width: 80px; color: #606266; }
.avatar-box {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid #e4e7ed;
}
.avatar { width: 100%; height: 100%; object-fit: cover; }
.avatar.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  color: #c0c4cc;
  font-size: 12px;
}
.input {
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
}
.pwd-group { display: flex; gap: 8px; flex-wrap: wrap; }
.btn-primary {
  padding: 6px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.list { display: flex; flex-direction: column; gap: 16px; }
.item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}
.thumb { width: 120px; height: 90px; object-fit: cover; border-radius: 4px; }
.meta { flex: 1; }
.name { margin: 0 0 4px 0; font-weight: 500; }
.status { margin: 0; font-size: 13px; }
.time { margin-left: 8px; color: #c0c4cc; }
.comment { margin: 4px 0 0 0; color: #909399; font-size: 13px; }
.tag-pending { color: #e6a23c; }
.tag-approved { color: #67c23a; }
.tag-rejected { color: #f56c6c; }
.ops { display: flex; gap: 8px; }
.btn-withdraw {
  padding: 6px 16px;
  background: #e6a23c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-delete {
  padding: 6px 16px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-withdraw:disabled, .btn-delete:disabled { opacity: 0.5; cursor: not-allowed; }
.count { color: #909399; margin-top: 20px; }
</style>
