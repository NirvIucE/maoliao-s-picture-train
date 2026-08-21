import axios, { type AxiosRequestConfig } from "axios"

const http = axios.create({
    baseURL: "/api",
    timeout: 10000,
})

// 请求拦截器：自动加 JWT
http.interceptors.request.use((config) => {
    const token = localStorage.getItem("token")
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// 响应拦截器：自动解包 .data  +  401 跳登录
http.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("token")
            window.location.href = "/login"
        }
        return Promise.reject(error)
    }
)

/*
 *   包装层
 *   解决 TypeScript 不知道拦截器已解包 AxiosResponse 的问题。
 *   api.get(...) 的返回值直接就是业务数据 { access_token, token_type }
 *   而不是 AxiosResponse<{ access_token, token_type }>
 */
const api = {
    get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
        return http.get(url, config) as any
    },
    post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.post(url, data, config) as any
    },
    put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.put(url, data, config) as any
    },
    patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.patch(url, data, config) as any
    },
    delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
        return http.delete(url, config) as any
    },
}

export default api
