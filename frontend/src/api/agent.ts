import api from "./client"

export interface ModelInfo {
    id: string
    name: string
    type: string
}

// 获取可用模型列表
export async function getAvailableModels(): Promise<ModelInfo[]> {
    return api.get("/agent/models")
}

// 图片分析（SSE 流式）
export async function* analyzeImageStream(
    imageId: number,
    model: string
): AsyncGenerator<string, void, unknown> {
        const token = localStorage.getItem("token")
        const response = await fetch("/api/agent/analyze-image", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                image_id: imageId,
                model
            })
    })
    
    if (!response.ok){
        const err = await response.json()
        throw new Error(err.detail || "分析失败")
    }

    const reader = response.body?.getReader()
    if(!reader) throw new Error("无法读取响应流")

    const decoder = new TextDecoder()
    let buffer = ""

    while(true){
        const { done, value } = await reader.read()
        if(done) break

        buffer += decoder.decode(value, {stream: true})
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for(const line of lines){
            if(line.startsWith("data: ")) {
                const data = line.slice(6)
                if (data === "[DONE]") return
                try{
                    const parsed = JSON.parse(data)
                    if(parsed.chunk) yield parsed.chunk
                } catch{
                    //忽略解析失败的行
                }
            }
        }
    }
}

// 对话 (SSE流式)
export async function* chatStream(
    messages: {role: string, content: string}[],
    model: string,
    imageId?: number
): AsyncGenerator<string, void, unknown> {
    const token = localStorage.getItem("token")
    const body: Record<string, any> = { messages, model }
    if (imageId){
        body.image_id = imageId
    }    
    const response = await fetch("/api/agent/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body)
    })

    if (!response.ok){
        const err = await response.json()
        throw new Error(err.detail || "对话失败")
    }

    const reader = response.body?.getReader()
    if(!reader) throw new Error("无法读取响应流")

    const decoder = new TextDecoder()
    let buffer = ""

    while(true){
        const{ done, value } = await reader.read()
        if(done) break

        buffer += decoder.decode(value, {stream: true})
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for(const line of lines) {
            if(line.startsWith("data:")) {
                const data = line.slice(6)
                if (data === "[DONE]") return
                try{
                    const parsed = JSON.parse(data)
                    if(parsed.chunk){
                        yield parsed.chunk
                    }
                } catch{
                    //忽略解析失败的行
                }
            }
        }
    }
}