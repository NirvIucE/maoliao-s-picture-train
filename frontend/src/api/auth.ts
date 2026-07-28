import api from "./client"

export async function login(username: string, password: string){
    const formData = new FormData()
    formData.append("username", username)
    formData.append("password", password)
    return api.post("/auth/login", formData, {
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    })
}

export async function register(username: string, email: string, password: string){
    return api.post("/auth/register", { username, email, password })
}

export async function getCurrentUser(){
    return api.get("/users/me")
}