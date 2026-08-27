// 路由表 + 导航守卫
import {
    createRouter, createWebHistory
} from "vue-router"

const router = createRouter({
    history: createWebHistory(),
    routes : [
        {
            path: "/login",
            name: "Login",
            component: () => import("@/views/Login.vue"),
        },
        {
            path: "/register",
            name: "Register",
            component: () => import("@/views/Register.vue"),
        },
        {
            path: "/gallery",
            name: "Gallery",
            component: () => import("@/views/Gallery.vue"),
            meta: { requiresAuth: true }, 
        },
        {
            path: "/upload",
            name: "Upload",
            component: () => import("@/views/Upload.vue"),
            meta: { requiresAuth: true },
        },
        {
            path: "/agent",
            name: "AgentChat",
            component: () => import("@/views/AgentChat.vue"),
            meta: { requiresAuth: true },
        },
        {
            path: "/detail/:id",
            name: "Detail",
            component: () => import("@/views/Detail.vue"),
            meta: { requiresAuth: true },
        },
        {
            path: "/public",
            name: "PublicGallery",
            component: () => import("@/views/PublicGallery.vue"),
        },
        {
            path: "/public/:id",
            name: "PublicDetail",
            component: () => import("@/views/PublicDetail.vue"),
        },
        {
            path: "/admin/review",
            name: "AdminReview",
            component: () => import("@/views/AdminReview.vue"),
            meta: { requiresAuth: true },
        },
        {
            path: "/profile",
            name: "Profile",
            component: () => import("@/views/Profile.vue"),
            meta: { requiresAuth: true },
        },
        {
            path: "/",
            redirect: "/public",
        },
    ],
})

// 导航首位：未登录跳转登录页
router.beforeEach((to, _from, next) => {
    const token = localStorage.getItem("token")
    if(to.meta.requiresAuth && !token){
        next("/login")
    }else if((to.path === "/login" || to.path === "/register") && token){
        next("/gallery")
    }else{
        next()
    }
})

export default router