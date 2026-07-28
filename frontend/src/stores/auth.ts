import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { login as loginApi, register as registerApi, getCurrentUser } from "@/api/auth"

export const useAuthStore = defineStore("auth", () => {
    const token = ref(localStorage.getItem("token") || "")
    const user = ref<any>(null)

    const isLoggedIn = computed(() => !!token.value)

    async function login(username: string, password: string){
        const res = await loginApi(username, password)
        token.value = res.access_token
        localStorage.setItem("token", res.access_token)
        await fetchUser()
    }

    async function register(username: string, email: string, password: string){
        await registerApi(username, email, password)
    }

    async function fetchUser(){
        if(!token.value) return
        user.value = await getCurrentUser()
    }

    function logout(){
        token.value = ""
        user.value = null
        localStorage.removeItem("token")
    }

    return {
        token,
        user,
        isLoggedIn,
        login,
        register,
        fetchUser,
        logout
    }
})