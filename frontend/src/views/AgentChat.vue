<!--
 * @Author: NirvIucE 1750682685@qq.com
 * @Date: 2026-07-28 15:46:24
 * @LastEditors: NirvIucE 1750682685@qq.com
 * @LastEditTime: 2026-07-31 16:32:33
 * @FilePath: \new-picture-train\frontend\src\views\AgentChat.vue
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
<!-- AI 助手页 -->
<script setup lang="ts">
import { ref, nextTick } from "vue"
import { getAvailableModels, chatStream, type ModelInfo } from "@/api/agent"

interface Message {
  role: "user" | "assistant"
  content: string
}

const models = ref<ModelInfo[]>([])
const selectedModel = ref("deepseek-chat")
const messages = ref<Message[]>([])
const input = ref("")
const sending = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

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

async function sendMessage() {
  const text = input.value.trim()
  if (!text || sending.value) return

  input.value = ""
  messages.value.push({ role: "user", content: text })

  // 添加空的 assistant 消息用于流式追加
  messages.value.push({ role: "assistant", content: "" })
  const assistantIndex = messages.value.length - 1

  sending.value = true
  try {
    const stream = chatStream(
      messages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
      selectedModel.value
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
          <p>可以问我关于你图库的问题，或者聊点别的。</p>
      </div>
      <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['message', msg.role === 'user' ? 'user' : 'assistant']"
        >
        <div class="msg-content">{{ msg.content }}</div>
      </div>
    </div> 

    <div class="chat-input">
      <input
        v-model="input"
        type="text"
        placeholder="输入消息..."
        :disabled="sending"
        @keyup.enter="sendMessage"
      />
      <button :disabled="!input.trim() || sending" @click="sendMessage">
        {{ sending ? "发送中..." : "发送" }}
      </button>
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