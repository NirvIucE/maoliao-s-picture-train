<!-- 注册页 -->
<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const auth = useAuthStore()

const username = ref("")
const email = ref("")
const password = ref("")
const errorMsg = ref("")
const successMsg = ref("")
const loading = ref(false)

async function handleRegister(){
    errorMsg.value = ""
    successMsg.value = ""
    loading.value = true
    try {
        await auth.register(username.value, email.value, password.value)
        successMsg.value = "注册成功！正在跳转登录..."
        setTimeout(() => router.push("/login"), 1500)
    } catch (err: any) {
        errorMsg.value = err.response?.data?.detail || "注册失败"
    } finally {
        loading.value = false
    }
}

</script>
<template>
    <div class="auth-container">
        <h2>注册猫里奥云图库</h2>
        <form @submit.prevent="handleRegister">
            <div class="form-group">
                <label>用户名</label>
                <input v-model="username" type="text" required />
            </div>
            <div class="form-group">
                <label>邮箱</label>
                <input v-model="email" type="email" required />
            </div>
            <div class="form-group">
                <label>密码</label>
                <input v-model="password" type="password" required />
            </div>
            <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
            <p v-if="successMsg" class="success">{{ successMsg }}</p>
            <button type="submit" :disabled="loading">
                {{ loading ? "注册中..." : "注册" }}
            </button>
        </form>
        <p class="link">
            已有账号？<router-link to="/login">去登录</router-link>
        </p>
    </div> 
</template>

<style scoped>
    .auth-container { max-width: 400px; margin: 80px auto; padding: 30px; border: 1px solid #ddd; border-radius: 8px; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; margin-bottom: 4px; font-weight: bold; }
    .form-group input { width: 100%; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 10px; background: #67c23a; color: white; border: none; border-radius: 4px; cursor: pointer; }
    button:disabled { background: #b3e19d; cursor: not-allowed; }
    .error { color: #f56c6c; margin-bottom: 12px; }
    .success { color: #67c23a; margin-bottom: 12px; }
    .link { text-align: center; margin-top: 16px; }
</style>
