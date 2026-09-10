import api from "./client"

// AI 任务（阶段 16：长任务异步化）
// 提交 → 轮询状态（轻量，不含图片）→ 完成后单独取结果
export type AITaskState = "pending" | "processing" | "completed" | "failed" | "cancelled"

export interface AITaskStatus {
    task_id: number
    status: AITaskState
    progress: number
    message: string | null
    error: string | null
}

export interface AITaskSubmitResponse {
    task_id: number
    status: AITaskState
}

export interface AITaskResult {
    task_id: number
    status: AITaskState
    image_base64: string
}

// 查询任务状态（轮询用，不含图片）
export function getTaskStatus(taskId: number): Promise<AITaskStatus> {
    return api.get(`/tasks/${taskId}`)
}

// 取任务结果图（仅 completed 可取，返回结果图 base64 data URL）
export function getTaskResult(taskId: number): Promise<AITaskResult> {
    return api.get(`/tasks/${taskId}/result`)
}

// 取消任务（幂等：已结束的任务原样返回）
export function cancelAITask(taskId: number): Promise<AITaskStatus> {
    return api.post(`/tasks/${taskId}/cancel`)
}
