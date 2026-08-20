<!--
 * @Author: NirvIucE 1750682685@qq.com
 * @Date: 2026-08-13 16:47:01
 * @LastEditors: NirvIucE 1750682685@qq.com
 * @LastEditTime: 2026-08-18 18:24:32
 * @FilePath: \new-picture-train\frontend\src\views\Detail.vue
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getImageDetail, editImage, replaceImage, uploadImage, aiEditImage, updateImageName, type ImageItem, type EditOperation } from "@/api/images"
import { removeBackground, type Config } from "@imgly/background-removal"

const route = useRoute()
const router = useRouter()

const image = ref<ImageItem | null>(null)
const loading = ref(true)
// 操作序列（按用户操作顺序，与后端执行顺序一致）
const operations = ref<EditOperation[]>([])

// 原图离屏 canvas（加载后固定不变）
const sourceCanvas = ref<HTMLCanvasElement | null>(null)
// 显示 canvas
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapper = ref<HTMLElement | null>(null)

// 裁剪框状态
const cropMode = ref(false)
const cropRect = ref({ left: 0, top: 0, right: 1, bottom: 1 })  // 百分比，相对当前显示

// 保存状态
const saving = ref(false)
const showSaveDialog = ref(false)   // 保存弹窗（选覆盖/另存）

const aiProcessing = ref(false)  // AI 抠图处理中
const aiProcessed = ref(false)   // 当前图片是否经过 AI 抠图

const aiResultType = ref<"remove-bg" | "ai-edit">("remove-bg")  // 区分抠图/区域编辑

// AI 区域编辑（涂鸦）状态
const aiEditMode = ref(false)        // 是否处于涂鸦模式
const aiEditPrompt = ref("")         // 编辑指令
const aiEditing = ref(false)         // 编辑请求处理中
const doodleCanvas = ref<HTMLCanvasElement | null>(null)  // 涂鸦层
const brushSize = ref<"small" | "medium" | "large">("medium")
const brushColor = ref("#ff0000")
const brushOpacity = 0.3   // 降低不透明度，让涂鸦下方的原图更清楚
const brushColors = [
  { color: "#ff0000", name: "红色" },
  { color: "#00aaff", name: "蓝色" },
  { color: "#00cc66", name: "绿色" },
  { color: "#ffcc00", name: "黄色" },
  { color: "#000000", name: "黑色" },
  { color: "#ffffff", name: "白色" },
]
const brushWidthMap: Record<string, number> = { small: 80, medium: 40, large: 15 }
const isDrawing = ref(false)
let lastPoint = { x: 0, y: 0 }

// AI 抠图配置：模型文件本地化，避免首次从境外 CDN 下载卡住
const removeBgConfig: Config = {
  publicPath: window.location.origin + "/background-removal/",
}

// 裁剪拖拽状态
const dragging = ref<null | {
  mode: "move" | "nw" | "ne" | "sw" | "se"
  startX: number
  startY: number
  startRect: typeof cropRect.value
  boxWidth: number
  boxHeight: number
}>(null)

// 图片 URL（带时间戳绕过缓存）
const imageUrl = computed(() => image.value?.image_url || "")

// 对单个 canvas 应用单个操作，返回新 canvas
function applyOperation(src: HTMLCanvasElement, op: EditOperation): HTMLCanvasElement{
    const out = document.createElement("canvas")
    const ctx = out.getContext("2d")!
    if (op.type === "rotate"){
        const angle = ((op.angle! % 360) + 360) % 360
        const swap = angle === 90 || angle === 270
        out.width = swap ? src.height : src.width
        out.height = swap ? src.width : src.height
        ctx.translate(out.width / 2, out.height / 2)
        ctx.rotate((angle * Math.PI) / 180)
        ctx.drawImage(src, -src.width / 2, -src.height / 2)
    }else if (op.type === "flip"){
        out.width = src.width
        out.height = src.height
        ctx.translate(src.width / 2, src.height / 2)
        ctx.scale(op.direction === "horizontal" ? -1 : 1, op.direction === "vertical" ? -1 : 1)
        ctx.drawImage(src, -src.width / 2, -src.height / 2)
    }else if (op.type === "crop"){
        const w = op.right! - op.left!
        const h = op.bottom! - op.top!
        out.width = w
        out.height = h
        ctx.drawImage(src, op.left!, op.top!, w, h, 0, 0, w, h)
    }
    return out
}

// 应用整个操作序列，返回当前图片状态
function applyOperations(src: HTMLCanvasElement | null, ops: EditOperation[]): HTMLCanvasElement | null{
    if (!src) return null
    let current = src
    for (const op of ops){
        current = applyOperation(current, op)
    }
    return current
}

// 当前图片状态（应用所有操作后）
const currentImage = computed(() => applyOperations(sourceCanvas.value, operations.value))

// 渲染显示 canvas
function render() {
  const canvas = canvasRef.value
  const current = currentImage.value
  if (!canvas || !current) return
  canvas.width = current.width
  canvas.height = current.height
  const ctx = canvas.getContext("2d")!
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(current, 0, 0)
}

// canvas 转 blob（PNG 格式，保留透明通道）
function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error("导出图片失败"))
    }, "image/png")
  })
}

// 加载图片到离屏 canvas
function loadImageToCanvas(url: string) {
  const img = new Image()
  img.crossOrigin = "anonymous"
  img.onload = () => {
    const c = document.createElement("canvas")
    c.width = img.naturalWidth
    c.height = img.naturalHeight
    c.getContext("2d")!.drawImage(img, 0, 0)
    sourceCanvas.value = c
    render()
  }
  img.src = url
}

// 操作变化时重新渲染
watch(currentImage, () => {
  nextTick(render)
})

// 进入涂鸦模式时，初始化涂鸦层尺寸并清空
watch(aiEditMode, (val) => {
  if(val){
    nextTick(() => {
      const dc = doodleCanvas.value
      const cur = currentImage.value
      if (dc && cur) {
        dc.width = cur.width
        dc.height = cur.height
        dc.getContext("2d")!.clearRect(0, 0, dc.width, dc.height)
      }
    })
  }
})

onMounted(async () => {
  try {
    const id = Number(route.params.id)
    image.value = await getImageDetail(id)
    loadImageToCanvas(imageUrl.value)
  } catch (err: any) {
    alert(err.response?.data?.detail || "加载失败")
    router.push("/gallery")
  } finally {
    loading.value = false
  }
})

function goBack() {
  router.push("/gallery")
}

// 追加操作
function addOperation(op: EditOperation) {
  operations.value.push(op)
}

function rotateCW() {
  addOperation({ type: "rotate", angle: 90 })
}
function flipH() {
  addOperation({ type: "flip", direction: "horizontal" })
}
function flipV() {
  addOperation({ type: "flip", direction: "vertical" })
}

// AI 抠图
async function handleRemoveBg() {
  if (!sourceCanvas.value || aiProcessing.value){
    return
  } 
  aiProcessing.value = true
  aiResultType.value = "remove-bg"
  try {
    const current = currentImage.value
    if (!current) return
    const blob = await canvasToBlob(current)
    const resultBlob = await removeBackground(blob, removeBgConfig)

    // 加载抠图结果
    const url = URL.createObjectURL(resultBlob)
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error("加载抠图结果失败"))
      img.src = url
    })
    const c = document.createElement("canvas")
    c.width = img.naturalWidth
    c.height = img.naturalHeight
    c.getContext("2d")!.drawImage(img, 0, 0)
    sourceCanvas.value = c
    operations.value = []
    aiProcessed.value = true
    URL.revokeObjectURL(url)
    render()
    alert("AI 抠图完成")
  } catch (err: any){
    alert("AI 抠图失败：" + (err?.message || err))
  } finally {
    aiProcessing.value = false
  }
}

// ===== AI 区域编辑（涂鸦 + 指令）=====
function enterAIEdit() {
  if (!currentImage.value || aiProcessing.value || aiEditing.value) return
  aiEditMode.value = true
  aiEditPrompt.value = ""
}

function cancelAIEdit() {
  aiEditMode.value = false
  aiEditPrompt.value = ""
  clearDoodle()
}

function clearDoodle() {
  const dc = doodleCanvas.value
  if (dc){
    dc.getContext("2d")!.clearRect(0, 0, dc.width, dc.height)
  }
}

// 鼠标坐标 → canvas 像素坐标（处理 CSS 缩放）
function getDoodlePoint(e: MouseEvent) {
  const dc = doodleCanvas.value!
  const rect = dc.getBoundingClientRect()
  return {
    x: (e.clientX - rect.left) * (dc.width / rect.width),
    y: (e.clientY - rect.top) * (dc.height / rect.height),
  }
}

function startDoodle(e: MouseEvent){
  isDrawing.value = true
  lastPoint = getDoodlePoint(e)
}

function drawDoodle(e: MouseEvent){
  if (!isDrawing.value) return
  const dc = doodleCanvas.value
  if (!dc) return
  const ctx = dc.getContext("2d")!
  const p = getDoodlePoint(e)
  const maxDim = Math.max(dc.width, dc.height)
  ctx.strokeStyle = brushColor.value
  ctx.globalAlpha = brushOpacity
  ctx.lineWidth = maxDim / brushWidthMap[brushSize.value]
  
  ctx.lineCap = "round"
  ctx.lineJoin = "round"
  ctx.beginPath()
  ctx.moveTo(lastPoint.x, lastPoint.y)
  ctx.lineTo(p.x, p.y)
  ctx.stroke()
  ctx.globalAlpha = 1
  lastPoint = p
}

function stopDoodle(){
  isDrawing.value = false
}

function blobToDataUrl(blob: Blob): Promise<string>{
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error("读取图片失败"))
    reader.readAsDataURL(blob)
  }
)}

async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const resp = await fetch(dataUrl)
  return await resp.blob()
}

async function handleAIEdit(){
  if (!image.value || aiEditing.value) return
  const prompt = aiEditPrompt.value.trim()
  if (!prompt) { alert("请输入编辑指令"); return }
  if (!currentImage.value) return

  aiEditing.value = true
  try {
    // 1. 合成提示图：当前图 + 红色涂鸦标记
    const cur = currentImage.value
    const dc = doodleCanvas.value
    const promptCanvas = document.createElement("canvas")
    promptCanvas.width = cur.width
    promptCanvas.height = cur.height
    const ctx = promptCanvas.getContext("2d")!
    ctx.drawImage(cur, 0, 0)
    if (dc) ctx.drawImage(dc, 0, 0)

    const blob = await canvasToBlob(promptCanvas)
    const imageBase64 = await blobToDataUrl(blob)
    // 2. 调后端 AI 编辑
    const colorName = brushColors.find(c => c.color === brushColor.value)?.name || "红色"
    const result = await aiEditImage(image.value.id, prompt, imageBase64, colorName)
    // 3. 结果 base64 → 图片 → 替换 sourceCanvas
    const resultBlob = await dataUrlToBlob(result.image_base64)
    const url = URL.createObjectURL(resultBlob)
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error("加载 AI 编辑结果失败"))
      img.src = url
    })
    const c = document.createElement("canvas")
    c.width = img.naturalWidth
    c.height = img.naturalHeight
    c.getContext("2d")!.drawImage(img, 0, 0)
    sourceCanvas.value = c
    operations.value = []
    aiProcessed.value = true
    aiResultType.value = "ai-edit"
    URL.revokeObjectURL(url)
    
    aiEditMode.value = false
    aiEditPrompt.value = ""
    render()
    alert("AI 编辑完成")

  }catch(err: any){
    alert("AI 编辑失败：" + (err?.response?.data?.detail || err?.message || err))
  }finally{
    aiEditing.value = false
  }
}

// 撤销最后一步
function undo() {
  operations.value.pop()
}

// 重置全部操作
function reset() {
  operations.value = []
  aiProcessed.value = false
  cropMode.value = false
  cropRect.value = { left: 0, top: 0, right: 1, bottom: 1 }
  // 重新加载原图（撤销抠图）
  if (image.value) {
    loadImageToCanvas(imageUrl.value)
  }
}

// 裁剪框
function enterCrop() {
  cropMode.value = true
  cropRect.value = { left: 0.05, top: 0.05, right: 0.95, bottom: 0.95 }
}

function cancelCrop() {
  cropMode.value = false
  cropRect.value = { left: 0, top: 0, right: 1, bottom: 1 }
}

function confirmCrop() {
  const current = currentImage.value
  if (!current) return
  const r = cropRect.value
  const isFull = r.left <= 0.001 && r.top <= 0.001 && r.right >= 0.999 && r.bottom >= 0.999
  if (!isFull) {
    // 换算成"当前图片状态"的像素坐标
    addOperation({
      type: "crop",
      left: Math.round(r.left * current.width),
      top: Math.round(r.top * current.height),
      right: Math.round(r.right * current.width),
      bottom: Math.round(r.bottom * current.height),
    })
  }
  cropMode.value = false
  cropRect.value = { left: 0, top: 0, right: 1, bottom: 1 }
}

// 裁剪框样式
const cropBoxStyle = computed(() => ({
  left: cropRect.value.left * 100 + "%",
  top: cropRect.value.top * 100 + "%",
  width: (cropRect.value.right - cropRect.value.left) * 100 + "%",
  height: (cropRect.value.bottom - cropRect.value.top) * 100 + "%",
}))

// 裁剪框拖拽（与之前 CSS 版相同逻辑）
function startDrag(e: MouseEvent, mode: "move" | "nw" | "ne" | "sw" | "se") {
  e.preventDefault()
  const box = canvasWrapper.value?.getBoundingClientRect()
  if (!box) return
  dragging.value = {
    mode,
    startX: e.clientX,
    startY: e.clientY,
    startRect: { ...cropRect.value },
    boxWidth: box.width,
    boxHeight: box.height,
  }
  document.addEventListener("mousemove", onDrag)
  document.addEventListener("mouseup", stopDrag)
}

function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  const d = dragging.value
  const dx = (e.clientX - d.startX) / d.boxWidth
  const dy = (e.clientY - d.startY) / d.boxHeight
  const r = { ...d.startRect }
  if (d.mode === "move") {
    const w = r.right - r.left
    const h = r.bottom - r.top
    r.left = clamp(d.startRect.left + dx, 0, 1 - w)
    r.top = clamp(d.startRect.top + dy, 0, 1 - h)
    r.right = r.left + w
    r.bottom = r.top + h
  } else {
    if (d.mode.includes("w")) r.left = clamp(d.startRect.left + dx, 0, d.startRect.right - 0.05)
    if (d.mode.includes("e")) r.right = clamp(d.startRect.right + dx, d.startRect.left + 0.05, 1)
    if (d.mode.includes("n")) r.top = clamp(d.startRect.top + dy, 0, d.startRect.bottom - 0.05)
    if (d.mode.includes("s")) r.bottom = clamp(d.startRect.bottom + dy, d.startRect.top + 0.05, 1)
  }
  cropRect.value = r
}

function stopDrag() {
  dragging.value = null
  document.removeEventListener("mousemove", onDrag)
  document.removeEventListener("mouseup", stopDrag)
}

function clamp(v: number, min: number, max: number) {
  return Math.min(Math.max(v, min), max)
}

onBeforeUnmount(() => {
  document.removeEventListener("mousemove", onDrag)
  document.removeEventListener("mouseup", stopDrag)
})

// 保存
function openSaveDialog() {
  if (operations.value.length === 0 && !aiProcessed.value) {
    alert("没有需要保存的修改")
    return
  }
  showSaveDialog.value = true
}

async function handleSave(mode: "overwrite" | "new") {
  if (!image.value) return
  saving.value = true
  try {
    if (aiProcessed.value) {
      // AI 抠图结果：导出当前 canvas 为 PNG blob
      const current = currentImage.value
      if (!current) return
      const blob = await canvasToBlob(current)
      if (mode === "overwrite") {
        await replaceImage(image.value.id, blob)
      } else {
        const suffix = aiResultType.value === "ai-edit" ? "(AI编辑)" : "(抠图)"
        const file = new File([blob], `${image.value.display_name}${suffix}.png`, { type: "image/png" })
        await uploadImage(file, `${image.value.display_name}${suffix}`)
      }
    }else {
      // 纯基础编辑：走 edit 接口
      await editImage(image.value.id, operations.value, mode)
    }
    
    if (mode === "new") {
      alert("已另存为新图片")
      showSaveDialog.value = false
      router.push("/gallery")
    } else {
      alert("已覆盖保存")
      showSaveDialog.value = false
      // 重新加载原图
      const id = image.value.id
      operations.value = []
      aiProcessed.value = false
      const fresh = await getImageDetail(id)
      image.value = fresh
      loadImageToCanvas(`${fresh.image_url}?t=${Date.now()}`)
    }
  } catch (err: any) {
    alert(err.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

// ===== 修改图片名称 =====
const renaming = ref(false)
const newName = ref("")
const renamingSaving = ref(false)

function startRename() {
  newName.value = image.value?.display_name || ""
  renaming.value = true
}

function cancelRename() {
  renaming.value = false
  newName.value = ""
}

async function confirmRename() {
  if (!image.value || renamingSaving.value) return
  renamingSaving.value = true
  try {
    const updated = await updateImageName(image.value.id, newName.value.trim())
    image.value = updated
    renaming.value = false
  } catch (err: any) {
    alert(err.response?.data?.detail || "修改名称失败")
  } finally {
    renamingSaving.value = false
  }
}
</script>

<template>
    <div class="detail-page">
        <div class="detail-header">
            <button class="btn-back" @click="goBack">← 返回图库</button>
            <h2>{{ image?.display_name || "图片详情" }}</h2>
        </div>

        <p v-if="loading">加载中...</p>

        <div v-else-if="image" class="detail-body">
            <!-- 左侧预览 -->
            <div class="preview-area">
                <div class="preview-box">
                    <div class="canvas-wrapper" ref="canvasWrapper">
                        <canvas ref="canvasRef" class="preview-canvas"></canvas>
                        <!-- 涂鸦层（AI 编辑模式） -->
                        <canvas v-if="aiEditMode" 
                          ref="doodleCanvas" 
                          class="doodle-canvas"
                          @mousedown="startDoodle" @mousemove="drawDoodle"
                          @mouseup="stopDoodle" @mouseleave="stopDoodle">
                        </canvas>
                        <!-- 裁剪框 -->
                        <div v-if="cropMode" class="crop-overlay">
                            <div class="crop-box" :style="cropBoxStyle"
                            @mousedown.stop="startDrag($event, 'move')"
                            >
                                <div class="crop-handle nw" @mousedown.stop="startDrag($event, 'nw')"></div>
                                <div class="crop-handle ne" @mousedown.stop="startDrag($event, 'ne')"></div>
                                <div class="crop-handle sw" @mousedown.stop="startDrag($event, 'sw')"></div>
                                <div class="crop-handle se" @mousedown.stop="startDrag($event, 'se')"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <!-- 右侧工具栏 -->
            <div class="toolbar">
                <h3>基础编辑</h3>
                <div class="tool-group">
                    <button class="tool-btn" @click="rotateCW">旋转 90°</button>
                    <button class="tool-btn" @click="flipH">水平翻转</button>
                    <button class="tool-btn" @click="flipV">垂直翻转</button>
                </div>
                <div class="tool-group">
                    <template v-if="!cropMode">
                        <button class="tool-btn" @click="enterCrop">裁剪</button>
                    </template>
                    <template v-else>
                        <button class="tool-btn primary" @click="confirmCrop">完成裁剪</button>
                        <button class="tool-btn" @click="cancelCrop">取消</button>
                    </template>
                    <div class="tool-group">
                        <button class="tool-btn" @click="undo" :disabled="operations.length === 0">撤销</button>
                        <button class="tool-btn" @click="reset" :disabled="operations.length === 0">重置</button>
                    </div>
                </div>
                <p v-if="operations.length > 0" class="ops-hint">
                    已记录 {{ operations.length }} 个操作
                </p>
                <h3>AI 编辑</h3>
                <div class="tool-group">
                  <button class="tool-btn" @click="handleRemoveBg" :disabled="aiProcessing || aiEditing || aiEditMode">
                    {{ aiProcessing ? "抠图中..." : "AI 抠图" }}
                  </button>
                  <template v-if="!aiEditMode">
                    <button class="tool-btn" @click="enterAIEdit" :disabled="aiProcessing || aiEditing">
                      AI 区域编辑
                    </button>
                  </template>
                  <template v-else>
                    <button class="tool-btn" @click="clearDoodle">
                      清除涂鸦
                    </button>
                    <button class="tool-btn" @click="cancelAIEdit">
                      取消
                    </button>
                  </template>
                </div>
                <div v-if="aiEditMode" class="ai-edit-panel">
                  <div class="brush-row">
                    <span class="brush-label">粗细：</span>
                    <button class="tool-btn" :class="{ active: brushSize === 'small' }" @click="brushSize = 'small'">
                      细
                    </button>
                    <button class="tool-btn" :class="{ active: brushSize === 'medium' }" @click="brushSize = 'medium'">
                      中
                    </button>
                    <button class="tool-btn" :class="{ active: brushSize === 'large' }" @click="brushSize = 'large'">
                      粗
                    </button>
                  </div>

                  <div class="brush-row">
                    <span class="brush-label">颜色：</span>
                    <button v-for="c in brushColors" 
                      :key="c.color" class="color-dot"
                      :style="{ background: c.color }" 
                      :title="c.name"
                      :class="{ active: brushColor === c.color }" 
                      @click="brushColor = c.color">
                    </button>
                  </div>

                  <input v-model="aiEditPrompt" class="ai-edit-input" placeholder="描述修改内容，如：换成星空" />
                  <button class="tool-btn primary" @click="handleAIEdit" :disabled="aiEditing">
                      {{ aiEditing ? "编辑中..." : "提交编辑" }}
                  </button>
                </div>
                <p v-if="aiEditMode" class="ops-hint">用鼠标在图片上涂抹要修改的区域（红色标记），再输入指令</p>
                <h3>图片信息</h3>
                <ul class="info-list">
                    <li>
                        <div class="name-row">
                            <template v-if="!renaming">
                                <span class="name-text">名称：{{ image.display_name }}</span>
                                <button class="tool-btn rename-btn" @click="startRename">改名</button>
                            </template>
                            <template v-else>
                                <input v-model="newName" class="rename-input" placeholder="输入新名称" @keyup.enter="confirmRename" />
                                <button class="tool-btn" @click="confirmRename" :disabled="renamingSaving">确定</button>
                                <button class="tool-btn" @click="cancelRename" :disabled="renamingSaving">取消</button>
                            </template>
                        </div>
                    </li>
                    <li>尺寸：{{ image.width }} × {{ image.height }}</li>
                    <li>大小：{{ (image.file_size / 1024).toFixed(1) }} KB</li>
                    <li>上传时间：{{ new Date(image.created_at).toLocaleString() }}</li>
                </ul>
            </div>
        </div>
        <!-- 底部保存按钮 -->
        <div v-if="image && !loading" class="detail-footer">
            <button class="btn-save" @click="openSaveDialog" :disabled="saving">保存修改</button>
        </div>
        <!-- 保存弹窗 -->
        <div v-if="showSaveDialog" class="dialog-overlay" @click.self="showSaveDialog = false">
            <div class="dialog">
                <h3>保存图片</h3>
                <p>选择保存方式：</p>
                <div class="dialog-actions">
                    <button class="btn-primary" :disabled="saving" @click="handleSave('overwrite')">
                        覆盖原图
                    </button>
                    <button class="btn-new" :disabled="saving" @click="handleSave('new')">
                        另存为新图
                    </button>
                    <button class="btn-cancel" @click="showSaveDialog = false">
                        取消
                    </button>
                </div>
                <p class="dialog-hint">另存为新图时，新图名称默认为「原名(编辑)」</p>
            </div>
        </div>
    </div>
</template>


<style scoped>
.detail-page { max-width: 1000px; margin: 0 auto; padding: 20px 0; }
.detail-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.detail-header h2 { margin: 0; }
.btn-back { padding: 6px 14px; border: 1px solid #ccc; background: white; border-radius: 4px; cursor: pointer; }
.btn-back:hover { background: #f5f5f5; }

.detail-body { display: flex; gap: 24px; align-items: flex-start; }

.preview-area { flex: 1; min-width: 0; }
.preview-box {
  position: relative;
  width: 100%;
  min-height: 400px;
  background: #f0f0f0;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.canvas-wrapper {
  position: relative;
  display: inline-block;
  line-height: 0;
}
.preview-canvas {
  max-width: 100%;
  max-height: 500px;
  display: block;
}

.doodle-canvas {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  touch-action: none;
}

.ai-edit-panel { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }

.ai-edit-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
}

.crop-overlay { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.4); }
.crop-box { position: absolute; border: 2px dashed #409eff; background: rgba(64, 158, 255, 0.1); cursor: move; }
.crop-handle { position: absolute; width: 12px; height: 12px; background: white; border: 2px solid #409eff; border-radius: 2px; }
.crop-handle.nw { left: -7px; top: -7px; cursor: nw-resize; }
.crop-handle.ne { right: -7px; top: -7px; cursor: ne-resize; }
.crop-handle.sw { left: -7px; bottom: -7px; cursor: sw-resize; }
.crop-handle.se { right: -7px; bottom: -7px; cursor: se-resize; }

.brush-row { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.brush-label { color: #606266; }
.color-dot { width: 22px; height: 22px; border-radius: 50%; border: 2px solid #ccc; cursor: pointer; }
.color-dot.active { border-color: #409eff; box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3); }
.tool-btn.active { border-color: #409eff; color: #409eff; background: #ecf5ff; }

.toolbar { width: 240px; flex-shrink: 0; }
.toolbar h3 { margin: 16px 0 8px; font-size: 15px; }
.toolbar h3:first-child { margin-top: 0; }
.tool-group { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.tool-btn {
  padding: 6px 12px;
  border: 1px solid #ccc;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.tool-btn:hover { border-color: #409eff; color: #409eff; }
.tool-btn.primary { background: #409eff; color: white; border-color: #409eff; }
.tool-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ops-hint { font-size: 12px; color: #909399; margin: 8px 0; }
.info-list { list-style: none; padding: 0; margin: 0; }
.info-list li { padding: 6px 0; font-size: 13px; color: #606266; border-bottom: 1px solid #f0f0f0; word-break: break-all; }
.name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.name-text { flex: 1; word-break: break-all; }
.rename-btn { padding: 2px 8px; font-size: 12px; flex-shrink: 0; }
.rename-input { flex: 1; min-width: 100px; padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; box-sizing: border-box; }

.detail-footer { margin-top: 20px; text-align: right; }
.btn-save { padding: 10px 28px; background: #409eff; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-save:disabled { background: #ccc; cursor: not-allowed; }

.dialog-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.dialog { background: white; border-radius: 10px; padding: 24px; width: 360px; }
.dialog h3 { margin: 0 0 12px; }
.dialog-actions { display: flex; gap: 10px; margin-top: 12px; }
.btn-primary { flex: 1; padding: 10px; background: #409eff; color: white; border: none; border-radius: 6px; cursor: pointer; }
.btn-new { flex: 1; padding: 10px; background: #67c23a; color: white; border: none; border-radius: 6px; cursor: pointer; }
.btn-cancel { padding: 10px 16px; border: 1px solid #ccc; background: white; border-radius: 6px; cursor: pointer; }
.btn-primary:disabled, .btn-new:disabled { opacity: 0.6; cursor: not-allowed; }
.dialog-hint { margin: 12px 0 0; font-size: 12px; color: #909399; }
</style>