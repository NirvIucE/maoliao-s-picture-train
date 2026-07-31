<script setup lang="ts">
import {ref, watch} from "vue"

import { analyzeImageStream , getAvailableModels, type ModelInfo} from "@/api/agent"
import type { ImageItem } from "@/api/images"


const props = defineProps<{ image: ImageItem | null; visible: boolean}>()

const emit = defineEmits<{close: []}>()

const result = ref("")
const analyzing = ref(false)
const errorMsg = ref("")

// 模型选择
const models = ref<ModelInfo[]>([])
const selectedModel = ref("")

// 弹窗打开时加载模型列表
watch(() => props.visible, async (val) => {
    if (val) {
        result.value = ""
        errorMsg.value = ""
        analyzing.value = false
        // 加载可用视觉模型
        try {
            const all = await getAvailableModels()
            models.value = all.filter((m) => m.type === "vision")
            if (models.value.length > 0 && !selectedModel.value) {
            selectedModel.value = models.value[0].id
            }
        } catch {
            errorMsg.value = "加载模型列表失败"
        }
    }
})

async function startAnalyze() {
    if (!props.image || analyzing.value) return

    analyzing.value = true
    result.value = ""
    errorMsg.value = ""

    try {
        const stream = analyzeImageStream(props.image.id, selectedModel.value)
        for await (const chunk of stream) {
            result.value += chunk
        }
    } catch (error: any) {
        errorMsg.value = error.message || "分析失败"
    } finally {
        analyzing.value = false
    }
}

watch(() => props.visible, (val) => {
    if (!val) {
        result.value = ""
        analyzing.value = false
        errorMsg.value = ""
        startAnalyze()
    }
})
</script>

<template>
    <div v-if="visible" class="dialog-overlay" @click.self="emit('close')">
        <div class="dialog">
            <div class="dialog-header">
                <h3>AI 图片分析</h3>
                <button class="btn-close" @click="emit('close')">✕</button>
            </div>
            <div class="dialog-body">
                <div class="preview" v-if="image">
                    <img
                        :src="image.thumbnail_url || image.image_url || ''"
                        :alt="image.display_name"
                    />
                    <p>{{ image.display_name }}</p>
                </div>
                <div class="result">
                    <!-- 模型选择 + 开始按钮 -->
                    <div class="model-row" v-if="!analyzing && !result">
                        <select v-model="selectedModel">
                            <option v-for="m in models" :key="m.id" :value="m.id">
                                {{ m.name }}
                            </option>
                        </select>
                        <button :disabled="!selectedModel" @click="startAnalyze">
                            开始分析
                        </button>
                    </div>
                    <p v-if="analyzing" class="status">🤖 AI 正在分析中...</p>
                    <pre v-if="result">{{ result }}</pre>
                    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dialog {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 700px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
}
.dialog-header h3 { margin: 0; }
.btn-close {
  border: none; background: none;
  font-size: 18px; cursor: pointer;
  color: #909399;
}
.dialog-body {
  padding: 20px;
  overflow-y: auto;
  display: flex;
  gap: 20px;
}
.preview {
  flex-shrink: 0;
  width: 200px;
}
.preview img {
  width: 100%;
  border-radius: 8px;
}
.preview p {
  margin: 8px 0 0;
  font-size: 13px;
  color: #606266;
  text-align: center;
}
.result { flex: 1; min-width: 0; }
.model-row { display: flex; gap: 10px; margin-bottom: 16px; }
.model-row select { flex: 1; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
.model-row button { padding: 8px 20px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; }
.model-row button:disabled { background: #ccc; cursor: not-allowed; }
.status { color: #409eff; }
pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
.error { color: #f56c6c; }
</style>