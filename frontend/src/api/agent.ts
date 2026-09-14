import api from "./client"

export interface ModelInfo {
    id: string
    name: string
    type: string
    // 阶段 20：是否支持 function calling（后端按 MODEL_REGISTRY 的 tools 标记给出）
    tools?: boolean
}

// 阶段 20：对话流的结构化事件
// 工具循环在后端单次请求内闭环，前端只消费这些事件，不需要理解 OpenAI 的 tool 消息协议
export interface ToolCallEvent {
    type: "tool_call"
    name: string
    args: Record<string, unknown>
}

export interface ToolResultEvent {
    type: "tool_result"
    name: string
    ok: boolean
    summary: string
    data: any
}

export interface ConfirmEvent {
    type: "confirm"
    action: string
    payload: { image_id: number; display_name: string; tags: string[] }
}

export type AgentEvent =
    | { type: "text"; content: string }
    | ToolCallEvent
    | ToolResultEvent
    | ConfirmEvent

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
// 阶段 20：出参从「纯文本」升级为结构化事件，以承载工具调用步骤与确认卡片
export async function* chatStream(
    messages: {role: string, content: string}[],
    model: string,
    imageId?: number
): AsyncGenerator<AgentEvent, void, unknown> {
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
                const data = line.slice(5).trim()
                if (data === "[DONE]") return
                try{
                    const parsed = JSON.parse(data)
                    // 文本增量仍是既有的 {"chunk": ...} 契约
                    if(parsed.chunk){
                        yield { type: "text", content: parsed.chunk }
                    } else if (parsed.type){
                        yield parsed as AgentEvent
                    }
                } catch{
                    //忽略解析失败的行
                }
            }
        }
    }
}