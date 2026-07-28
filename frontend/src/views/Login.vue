<!-- 登录页 -->
<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const auth = useAuthStore()

const username = ref("")
const password = ref("")
const errorMsg = ref("")
const loading = ref(false)

async function handleLogin() {
    errorMsg.value = ""
    loading.value = true
    try {
        await auth.login(username.value, password.value)
        router.push("/gallery")
    } catch (err: any) {
        errorMsg.value = err.response?.data?.detail || "登录失败"
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <div class="auth-container">
        <h2>登录猫里奥云图库</h2>
        <form @submit.prevent="handleLogin">
            <div class="form-group">
                <label>用户名</label>
                <input v-model="username" type="text" required />
            </div>
            <div class="form-group">
                <label>密码</label>
                <input v-model="password" type="password" required />
            </div>
            <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
            <button type="submit" :disabled="loading">
                {{ loading ? "登录中..." : "登录" }}
            </button>
        </form>
        <p class="link">
            还没有账号？<router-link to="/register">去注册</router-link>
        </p>
    </div>
</template>

<style scoped>
.auth-container {
    max-width: 400px;
    margin: 80px auto;
    padding: 30px;
    border: 1px solid #ddd;
    border-radius: 8px;
}
.form-group {
    margin-bottom: 16px;
}
.form-group label {
    display: block;
    margin-bottom: 4px;
    font-weight: bold;
}
.form-group input {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-sizing: border-box;
}
button {
    width: 100%;
    padding: 10px;
    background: #409eff;
    color: #fff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
button:disabled {
    background: #a0cfff;
    cursor: not-allowed;
}
.error {
    color: #f56c6c;
    margin-bottom: 12px;
}
.link {
    text-align: center;
    margin-top: 16px;
}
</style>