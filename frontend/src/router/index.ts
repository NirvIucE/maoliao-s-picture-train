/*
 * @Author: NirvIucE 1750682685@qq.com
 * @Date: 2026-07-27 21:08:43
 * @LastEditors: NirvIucE 1750682685@qq.com
 * @LastEditTime: 2026-08-13 16:40:14
 * @FilePath: \new-picture-train\frontend\src\router\index.ts
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */

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
            path: "/",
            redirect: "/gallery",
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