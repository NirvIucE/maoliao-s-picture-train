
<!-- AI 助手页 -->
<script setup lang="ts">
import { ref, nextTick } from "vue"
import { getAvailableModels, chatStream, type ModelInfo } from "@/api/agent"
import { uploadImage, type ImageItem } from "@/api/images"
import { submitToPublic } from "@/api/public"
import GalleryPicker from "@/views/GalleryPicker.vue"

// 工具调用步骤：把后端事件翻译成用户看得懂的一行（阶段 20）
interface ToolStep {
  name: string
  label: string
  status: "running" | "done" | "failed"
  summary: string
  items: { id: number; display_name: string; thumbnail_url: string }[]
}

// 待确认的写操作：AI 只准备参数，真正提交由用户点卡片触发
interface ConfirmCard {
  action: string
  imageId: number
  displayName: string
  tags: string[]
  submitting: boolean
  done: boolean
  error: string
}

interface Message {
  role: "user" | "assistant"
  content: string
  imageUrl?: string
  imageName?: string
  steps?: ToolStep[]
  confirm?: ConfirmCard
}

const TOOL_LABELS: Record<string, string> = {
  search_images: "检索个人图库",
  get_image_info: "查看图片详情",
  submit_to_public: "准备提交公共图库",
}

const models = ref<ModelInfo[]>([])
const selectedModel = ref("deepseek-chat")
const messages = ref<Message[]>([])
const input = ref("")
const sending = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

// 附件图片状态
const attachedImage = ref<{
  id: number
  thumbnail_url: string
  display_name: string
} | null>(null)
const uploadLoading = ref(false)
// 上传失败反馈消息（替代 alert）
const errorMsg = ref("")
let previousModel = "" // 记住上传前选择的模型 

const galleryVisible = ref(false) //图库弹窗显隐

// 加载可用模型
async function loadModels() {
  try {
    models.value = await getAvailableModels()
    // 默认选第一个文本模型
    const textModel = models.value.find((m) => m.type === "text")
    if (textModel) selectedModel.value = textModel.id
  } catch {
    // 忽略
  }
}

loadModels()

// 触发文件选择
function triggerUpload() {
  fileInput.value?.click()
}

// 文件选择 + 上传
async function handleFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if(!file) return

  uploadLoading.value = true
  errorMsg.value = ""
  try {
    const result = await uploadImage(file)
    attachedImage.value = {
      id: result.id,
      thumbnail_url: result.thumbnail_url,
      display_name: result.display_name,
    }
    // 自动切换到视觉模型
    const visionModel = models.value.find((m) => m.type === "vision")
    if (visionModel){
      previousModel = selectedModel.value
      selectedModel.value = visionModel.id
    }
  }
  catch (err : any){
    errorMsg.value = err.response?.data?.detail || "上传失败"
  }
  finally {
    uploadLoading.value = false
    target.value = ""  // 清空，允许重复选同一文件
  }
}

// 移除附件
function removeAttachedImage() {
  attachedImage.value = null
  if (previousModel) {
    selectedModel.value = previousModel
    previousModel = ""
  }
}

// 从图库弹窗选择图
function onGallerySelect(image: ImageItem) {
  attachedImage.value = {
    id: image.id,
    thumbnail_url: image.thumbnail_url || image.image_url || "",
    display_name: image.display_name,
  }
  galleryVisible.value = false
  // 自动切换到视觉模型
  const visionModel = models.value.find((m) => m.type === "vision")
  if(visionModel){
    previousModel = selectedModel.value
    selectedModel.value = visionModel.id
  }
}

async function sendMessage() {
  const text = input.value.trim()
  const hasImage = attachedImage.value !== null
  if ((!text && !hasImage) || sending.value) return

  // 构建用户消息 (含缩略图)
  const userMsg : Message= {
    role: "user",
    content: text || "对用户图片进行分析",
  }
  if (hasImage){
    userMsg.imageUrl = attachedImage.value!.thumbnail_url
    userMsg.imageName = attachedImage.value!.display_name
  }
  messages.value.push(userMsg)

  input.value = ""
  const imageId = attachedImage.value?.id
  attachedImage.value = null // 发生之后清除附件

  // 添加空的 assistant 消息用于流式追加
  messages.value.push({ role: "assistant", content: "" })
  const assistantIndex = messages.value.length - 1

  sending.value = true
  try {
    const stream = chatStream(
      messages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
      selectedModel.value,
      imageId
    )
    for await (const event of stream) {
      const msg = messages.value[assistantIndex]
      if (event.type === "text") {
        msg.content += event.content
      } else if (event.type === "tool_call") {
        if (!msg.steps) msg.steps = []
        msg.steps.push({
          name: event.name,
          label: TOOL_LABELS[event.name] || event.name,
          status: "running",
          summary: "",
          items: [],
        })
      } else if (event.type === "tool_result") {
        // 同名工具可能连续出现，配对它前面最近一个还在进行中的步骤
        const step = [...(msg.steps || [])]
          .reverse()
          .find((s) => s.name === event.name && s.status === "running")
        if (step) {
          step.status = event.ok ? "done" : "failed"
          step.summary = event.summary
          if (Array.isArray(event.data)) {
            // 只有带缩略图的检索结果才需要展示（详情类工具返回的是对象）
            step.items = event.data
              .filter((it: any) => it.thumbnail_url)
              .map((it: any) => ({
                id: it.id,
                display_name: it.display_name,
                thumbnail_url: it.thumbnail_url as string,
              }))
          }
        }
      } else if (event.type === "confirm") {
        msg.confirm = {
          action: event.action,
          imageId: event.payload.image_id,
          displayName: event.payload.display_name,
          tags: event.payload.tags || [],
          submitting: false,
          done: false,
          error: "",
        }
      }
      await nextTick()
      // 自动滚到底部
      if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight
      }
    }
  } catch (err: any) {
    messages.value[assistantIndex].content = `错误: ${err.message}`
  } finally {
    sending.value = false
  }
}

// 用户点确认卡片 —— 真正的写动作在这里发生（走既有 REST 端点，与普通提交面板同一条路径）
async function confirmSubmit(msg: Message) {
  const card = msg.confirm
  if (!card || card.submitting || card.done) return
  card.submitting = true
  card.error = ""
  try {
    await submitToPublic(card.imageId, card.tags)
    card.done = true
    msg.content += `${msg.content ? "\n" : ""}已提交《${card.displayName}》，等待管理员审核。`
  } catch (err: any) {
    card.error = err.response?.data?.detail || "提交失败"
  } finally {
    card.submitting = false
  }
}

function clearChat() {
  messages.value = []
  attachedImage.value = null 
}
</script>

<template>
  <div class="chat-page">
    <div class="chat-header">
       <h2>AI 助手</h2>
       <div class="chat-controls">
          <select v-model="selectedModel" :disabled="sending">
            <option v-for="m in models" :key="m.id" :value="m.id">
              {{ m.name }}（{{ m.type === "vision" ? "视觉" : "文本" }}）
            </option>
          </select>
          <button class="btn-clear" @click="clearChat">清空对话</button>
       </div>
    </div>

    <div ref="chatContainer" class="chat-messages">
      <div v-if="messages.length === 0" class="empty">
        <p>你好！我是猫里奥 AI 助手。</p>
          <p>可以问我关于图库的问题，或者上传图片让我帮你分析。</p>
          <p>也可以说「把那张猫猫的图提交到公共图库」，我查好后请你确认。</p>
      </div>
      <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['message', msg.role === 'user' ? 'user' : 'assistant']"
        >
        <div class="msg-content">
          <img
            v-if="msg.imageUrl"
            :src="msg.imageUrl"
            class="msg-image" 
          />
          <!-- 工具调用步骤（阶段 20）：检索到哪些图、查了哪张图 -->
          <div v-if="msg.steps && msg.steps.length" class="tool-steps">
            <div v-for="(step, si) in msg.steps" :key="si" class="tool-step">
              <span class="step-icon">
                {{ step.status === "running" ? "⏳" : step.status === "done" ? "✓" : "✕" }}
              </span>
              <span class="step-label">{{ step.label }}</span>
              <span v-if="step.summary" class="step-summary">{{ step.summary }}</span>
              <div v-if="step.items.length" class="step-thumbs">
                <img
                  v-for="it in step.items"
                  :key="it.id"
                  :src="it.thumbnail_url"
                  :title="it.display_name"
                  :alt="it.display_name"
                />
              </div>
            </div>
          </div>
          <div v-if="msg.content">{{ msg.content }}</div>
          <!-- 写操作确认卡片：AI 只负责准备参数，授权由用户点击给出 -->
          <div v-if="msg.confirm" class="confirm-card">
            <div class="confirm-title">待确认：提交到公共图库</div>
            <div class="confirm-row">
              图片：{{ msg.confirm.displayName }}（#{{ msg.confirm.imageId }}）
            </div>
            <div class="confirm-row">
              标签：{{ msg.confirm.tags.length ? msg.confirm.tags.join("、") : "无" }}
            </div>
            <p v-if="msg.confirm.error" class="confirm-error">{{ msg.confirm.error }}</p>
            <button
              class="btn-confirm"
              :disabled="msg.confirm.submitting || msg.confirm.done"
              @click="confirmSubmit(msg)"
            >
              {{ msg.confirm.done ? "已提交" : msg.confirm.submitting ? "提交中..." : "确认提交" }}
            </button>
          </div>
        </div>
      </div>
    </div> 
    <!-- 图库选图弹窗 -->
    <GalleryPicker
      :visible="galleryVisible"
      @close="galleryVisible = false"
      @select="onGallerySelect"
    />
    <!-- 隐藏文件选择器 -->
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      style="display: none"
      @change="handleFileSelected"
    />
    <div class="chat-input-area">
      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      <!-- 附件预览条 -->
      <div v-if="attachedImage" class="image-preview">
        <img :src="attachedImage.thumbnail_url" />
        <span class="preview-name">{{ attachedImage.display_name }}</span>
        <button class="btn-remove" @click="removeAttachedImage" :disabled="sending">✕</button>
      </div>
      <div class="chat-input">
        <button
          class="btn-upload"
          @click="triggerUpload"
          :disabled="sending || uploadLoading"
          title="上传新图片分析"
        >
          {{ uploadLoading ? "⏳" : "本地上传图片" }}
        </button>
        <button
          class="btn-upload"
          @click="galleryVisible = true"
          :disabled="sending"
          title="从图库选择图片"
        >
          从图库选图
        </button>
        <input
          v-model="input"
          type="text"
          placeholder="输入消息，或上传图片让我分析..."
          :disabled="sending"
          @keyup.enter="sendMessage"
        />
        <button :disabled="(!input.trim() && !attachedImage) || sending" @click="sendMessage">
          {{ sending ? "发送中..." : "发送" }}
        </button>
      </div>
    </div>
  </div> 
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  max-width: 800px;
  margin: 0 auto;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #e4e7ed;
}
.chat-header h2 { margin: 0; }
.chat-controls { display: flex; gap: 10px; align-items: center; }
.chat-controls select {
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.btn-clear {
  padding: 6px 12px;
  border: 1px solid #ccc;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}
.empty {
  text-align: center;
  color: #909399;
  margin-top: 60px;
}
.message {
  margin-bottom: 16px;
  display: flex;
}
.message.user { justify-content: flex-end; }
.msg-content {
  max-width: 70%;
  padding: 10px 16px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.message.user .msg-content {
  background: #409eff;
  color: white;
}
.message.assistant .msg-content {
  background: #f0f0f0;
  color: #303133;
}
.msg-image {
  display: block;
  max-width: 200px;
  max-height: 150px;
  border-radius: 6px;
  margin-bottom: 8px;
  object-fit: cover;
}
/* 工具调用步骤（阶段 20） */
.tool-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}
.tool-step {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  font-size: 13px;
  color: #606266;
}
.step-icon { color: #409eff; }
.step-label { font-weight: 600; }
.step-summary { color: #909399; }
.step-thumbs { display: flex; gap: 6px; }
.step-thumbs img {
  width: 36px;
  height: 36px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}
/* 写操作确认卡片 */
.confirm-card {
  margin-top: 8px;
  padding: 12px;
  background: #fff;
  border: 1px solid #409eff;
  border-radius: 8px;
}
.confirm-title {
  font-weight: 600;
  color: #409eff;
  margin-bottom: 6px;
}
.confirm-row {
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}
.confirm-error { color: #f56c6c; font-size: 13px; margin: 6px 0 0; }
.btn-confirm {
  margin-top: 10px;
  padding: 6px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.btn-confirm:disabled {
  background: #ccc;
  cursor: not-allowed;
}
.chat-input-area {
  border-top: 1px solid #e4e7ed;
}
.error-msg { color: #f56c6c; margin: 8px 0 0; }
.image-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  margin-bottom: 4px;
}
.image-preview img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #ddd;
}
.preview-name {
  flex: 1;
  font-size: 13px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-remove {
  border: none;
  background: none;
  font-size: 16px;
  color: #909399;
  cursor: pointer;
  padding: 2px 6px;
}
.btn-remove:hover { color: #f56c6c; }
.btn-remove:disabled { cursor: not-allowed; }
.btn-upload {
  padding: 10px 12px;
  background: #f0f0f0;
  border: 1px solid #ccc;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
.btn-upload:hover { background: #e0e0e0; }
.btn-upload:disabled { opacity: 0.5; cursor: not-allowed; }
.chat-input {
  display: flex;
  gap: 10px;
  padding: 12px 0;
  border-top: 1px solid #e4e7ed;
}
.chat-input input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
.chat-input button {
  padding: 10px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.chat-input button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>