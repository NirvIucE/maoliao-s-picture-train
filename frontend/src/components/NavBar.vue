<script setup lang="ts">
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const auth = useAuthStore()

</script>

<template>
    <nav class="navbar">
        <div class="nav-left">
            <router-link to="/" class="logo">猫里奥云图库</router-link>
            <router-link to="/public">公共图库</router-link>
        </div>
        <div class="nav-right">
            <template v-if="auth.isLoggedIn">
                <router-link to="/upload">上传</router-link>
                <router-link to="/gallery">我的图库</router-link>
                <router-link to="/agent">AI助手</router-link>
                <router-link v-if="auth.user?.role === 'admin'" to="/admin/review">审核</router-link>
                <router-link to="/profile" class="username">
                    <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="nav-avatar" alt="头像" />
                    {{ auth.user?.username }}
                </router-link>
                <button @click="auth.logout(); router.push('/login')">登出</button>
            </template>
            <template v-else>
                <router-link to="/profile">个人信息</router-link>
            </template>
        </div>
    </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.nav-left {
  display: flex;
  align-items: center;
  gap: 20px;
}
.nav-left .logo {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
  text-decoration: none;
}
.nav-left a:not(.logo) {
  color: #606266;
  text-decoration: none;
}
.nav-left a:not(.logo):hover {
  color: #409eff;
}
.nav-right {
  display: flex;
  align-items: center;
  gap: 20px;
}
.nav-right a {
  color: #606266;
  text-decoration: none;
}
.nav-right a:hover {
  color: #409eff;
}
.username {
  color: #909399;
  display: flex;
  align-items: center;
  gap: 6px;
}
.nav-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
}
button {
  padding: 6px 12px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style>