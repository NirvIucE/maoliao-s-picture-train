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
        </div>
        <div class="nav-right">
            <template v-if="auth.isLoggedIn">
                <router-link to="/upload">上传</router-link>
                <router-link to="/gallery">我的图库</router-link>
                <router-link to="/agent">AI助手</router-link>
                <span class="username">{{ auth.user?.username }}</span>
                <button @click="auth.logout(); router.push('/login')">登出</button>
            </template>
            <template v-else>
                <router-link to="/login">登录</router-link>
                <router-link to="/register">注册</router-link>
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
.nav-left .logo {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
  text-decoration: none;
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