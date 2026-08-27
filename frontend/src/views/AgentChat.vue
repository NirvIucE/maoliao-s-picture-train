
<!-- AI 助手页 -->
<script setup lang="ts">
import { ref, nextTick } from "vue"
import { getAvailableModels, chatStream, type ModelInfo } from "@/api/agent"
import { uploadImage, type ImageItem } from "@/api/images"
import GalleryPicker from "@/views/GalleryPicker.vue"

interface Message {
  role: "user" | "assistant"
  content: string
  imageUrl?: string
  imageName?: string
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
    for await (const chunk of stream) {
      messages.value[assistantIndex].content += chunk
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
          <div>{{ msg.content }}</div>
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