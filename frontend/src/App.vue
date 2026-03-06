<template>
  <div class="page">
    <!-- Header with Stats -->
    <header class="header">
      <StatsCards />
    </header>

    <!-- Hero -->
    <section class="hero">
      <div class="hero-text">
        <p class="eyebrow">脱敏与分片工具</p>
        <h1>上传文件，异步处理后下载结果。</h1>
        <p class="lead">
          同时支持 CSV/XLSX 脱敏与 PDF/TXT 分片。
          大文件会按 140MB 切分，并打包为 ZIP 下载。
        </p>
      </div>
    </section>

    <!-- Main Panels -->
    <section class="panel">
      <UploadCard
        :mode="mode"
        :uploading="uploading"
        :api-base-input="apiBaseInput"
        :effective-api-base-label="effectiveApiBaseLabel"
        :api-base-error="apiBaseError"
        :file-name="fileName"
        :has-file="!!selectedFile"
        @update:mode="switchMode"
        @update:api-base-input="apiBaseInput = $event"
        @save-api-base="saveApiBase"
        @clear-api-base="clearApiBase"
        @submit="uploadFile"
        @remove-file="removeFile"
        @file-change="handleFileChange"
      />

      <StatusCard
        :task-id="taskId"
        :status="status"
        :progress="progress"
        :localized-status-message="localizedStatusMessage"
        :error-message="errorMessage"
        @cancel="cancelTask"
        @download="downloadResults"
      />
    </section>

    <!-- Rules -->
    <RulesCard :mode="mode" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import StatsCards from './components/StatsCards.vue'
import UploadCard from './components/UploadCard.vue'
import StatusCard from './components/StatusCard.vue'
import RulesCard from './components/RulesCard.vue'

// =============== CONFIG ===============
const configuredApiBase = (import.meta.env.VITE_API_BASE_URL || '').trim()
const API_BASE_STORAGE_KEY = 'bulk_desensitizer_api_base'
const SPLIT_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024

// =============== UTILITIES ===============
const normalizeBaseUrl = (value) => {
  const trimmed = (value || '').trim()
  if (!trimmed) return ''

  const withProtocol = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : `${window.location.protocol}//${trimmed}`

  let parsed
  try {
    parsed = new URL(withProtocol)
  } catch {
    return ''
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    return ''
  }

  parsed.search = ''
  parsed.hash = ''
  const pathname = parsed.pathname.replace(/\/+$/, '')
  return `${parsed.origin}${pathname}`
}

const readApiBaseFromQuery = () => {
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('apiBase') || params.get('api_base') || params.get('backend')
  return normalizeBaseUrl(raw)
}

const readInitialApiBase = () => {
  const queryBase = readApiBaseFromQuery()
  if (queryBase) {
    window.localStorage.setItem(API_BASE_STORAGE_KEY, queryBase)
    return queryBase
  }

  const localBase = normalizeBaseUrl(window.localStorage.getItem(API_BASE_STORAGE_KEY) || '')
  if (localBase) return localBase
  return normalizeBaseUrl(configuredApiBase)
}

const buildApiUrl = (path) => {
  return apiBase.value ? `${apiBase.value}${path}` : path
}

const buildWsUrl = (path) => {
  if (apiBase.value) {
    const wsBase = apiBase.value.replace(/^http/i, 'ws')
    return `${wsBase}${path}`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}${path}`
}

const normalizeErrorMessage = (error) => {
  const message = error?.message || ''
  if (!message) return '发生未知错误'
  if (/failed to fetch/i.test(message)) {
    return apiBase.value
      ? `网络请求失败，请检查后端地址是否可访问：${apiBase.value}`
      : '网络请求失败。若前后端不在同一域名，请先填写后端地址。'
  }
  return message
}

const readErrorMessage = async (response, fallback = '请求失败') => {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string' && data.detail) {
        return data.detail
      }
    } catch {
      // ignore JSON parse errors and fallback to text below.
    }
  }

  try {
    const text = await response.text()
    if (text) return text
  } catch {
    // ignore read errors and fallback.
  }

  return fallback
}

const localizeStatusMessage = (message) => {
  if (!message) return ''

  if (message === 'queued') return '排队中'
  if (message === 'splitting file') return '正在切分文件'
  if (message === 'completed') return '已完成'
  if (message.startsWith('completed (') && message.endsWith(')')) {
    const detail = message.slice('completed ('.length, -1)
    return `已完成（${detail}）`
  }

  const processRowMatch = message.match(/^Processing row (\d+)\/(\d+)$/)
  if (processRowMatch) {
    return `正在处理第 ${processRowMatch[1]} / ${processRowMatch[2]} 行`
  }

  const desensitizeMatch = message.match(/^Desensitizing row (\d+)\/(\d+)$/)
  if (desensitizeMatch) {
    return `正在脱敏第 ${desensitizeMatch[1]} / ${desensitizeMatch[2]} 行`
  }

  return message
}

// =============== STATE ===============
const selectedFile = ref(null)
const fileName = ref('')
const uploading = ref(false)
const taskId = ref('')
const errorMessage = ref('')
const apiBaseError = ref('')
const mode = ref('desensitize')
const apiBaseInput = ref(readInitialApiBase())
const status = ref({
  state: 'IDLE',
  current: 0,
  total: 0,
  message: ''
})

const socket = ref(null)
const apiBase = computed(() => normalizeBaseUrl(apiBaseInput.value))
const effectiveApiBaseLabel = computed(() => apiBase.value || '同源（当前访问域名）')

const progress = computed(() => {
  if (!status.value.total) {
    return 0
  }
  const ratio = status.value.current / status.value.total
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
})

const localizedStatusMessage = computed(() => localizeStatusMessage(status.value.message))

// =============== ACTIONS ===============
const saveApiBase = () => {
  const raw = (apiBaseInput.value || '').trim()
  const normalized = normalizeBaseUrl(raw)

  if (raw && !normalized) {
    apiBaseError.value = '后端地址格式不正确，请输入完整 URL 或域名。'
    return
  }

  apiBaseError.value = ''
  apiBaseInput.value = normalized
  if (normalized) {
    window.localStorage.setItem(API_BASE_STORAGE_KEY, normalized)
  } else {
    window.localStorage.removeItem(API_BASE_STORAGE_KEY)
  }
}

const clearApiBase = () => {
  apiBaseError.value = ''
  apiBaseInput.value = ''
  window.localStorage.removeItem(API_BASE_STORAGE_KEY)
}

const switchMode = (nextMode) => {
  if (mode.value === nextMode) return
  mode.value = nextMode
  selectedFile.value = null
  fileName.value = ''
  errorMessage.value = ''
}

const handleFileChange = (file) => {
  selectedFile.value = file
  fileName.value = file ? file.name : ''
}

const removeFile = () => {
  selectedFile.value = null
  fileName.value = ''
}

// =============== UPLOAD ===============
const uploadSplitFileLegacy = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(buildApiUrl('/upload/split'), {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, '上传失败'))
  }

  return response.json()
}

const uploadSplitFileInChunks = async (file) => {
  const initResponse = await fetch(buildApiUrl('/upload/split/init'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name })
  })

  if (initResponse.status === 404) {
    return uploadSplitFileLegacy(file)
  }

  if (!initResponse.ok) {
    throw new Error(await readErrorMessage(initResponse, '初始化分片上传失败'))
  }

  const initData = await initResponse.json()
  const uploadId = initData.upload_id
  const totalChunks = Math.max(1, Math.ceil(file.size / SPLIT_UPLOAD_CHUNK_BYTES))

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    const start = chunkIndex * SPLIT_UPLOAD_CHUNK_BYTES
    const end = Math.min(file.size, start + SPLIT_UPLOAD_CHUNK_BYTES)
    const chunkBlob = file.slice(start, end)

    const formData = new FormData()
    formData.append('upload_id', uploadId)
    formData.append('chunk_index', String(chunkIndex))
    formData.append('total_chunks', String(totalChunks))
    formData.append('file', chunkBlob, `${file.name}.part${chunkIndex}`)

    const chunkResponse = await fetch(buildApiUrl('/upload/split/chunk'), {
      method: 'POST',
      body: formData
    })

    if (!chunkResponse.ok) {
      throw new Error(await readErrorMessage(chunkResponse, '分片上传失败'))
    }

    status.value = {
      state: 'PROGRESS',
      current: chunkIndex + 1,
      total: totalChunks,
      message: `上传分片 ${chunkIndex + 1}/${totalChunks}`
    }
  }

  const completeResponse = await fetch(buildApiUrl('/upload/split/complete'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ upload_id: uploadId })
  })

  if (!completeResponse.ok) {
    throw new Error(await readErrorMessage(completeResponse, '完成分片上传失败'))
  }

  return completeResponse.json()
}

const uploadFile = async () => {
  if (!selectedFile.value) {
    errorMessage.value =
      mode.value === 'split'
        ? '请先选择 PDF 或 TXT 文件。'
        : '请先选择 CSV 或 XLSX 文件。'
    return
  }

  errorMessage.value = ''
  uploading.value = true

  try {
    let data
    if (mode.value === 'split') {
      data = await uploadSplitFileInChunks(selectedFile.value)
    } else {
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      const response = await fetch(buildApiUrl('/upload/desensitize'), {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response, '上传失败'))
      }

      data = await response.json()
    }

    taskId.value = data.task_id
    status.value = {
      state: 'PENDING',
      current: 0,
      total: 0,
      message: 'queued'
    }

    connectWebSocket()
  } catch (error) {
    errorMessage.value = normalizeErrorMessage(error)
  } finally {
    uploading.value = false
  }
}

// =============== WEBSOCKET ===============
const connectWebSocket = () => {
  if (socket.value) {
    socket.value.close()
  }

  socket.value = new WebSocket(buildWsUrl(`/ws/status/${taskId.value}`))

  socket.value.onopen = () => {
    console.log('WS Connected')
  }

  socket.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      status.value.current = data.current
      status.value.total = data.total
      status.value.message = data.message

      if (typeof data.message === 'string' && data.message.startsWith('completed')) {
        status.value.state = 'SUCCESS'
        socket.value.close()
      } else {
        status.value.state = 'PROGRESS'
      }
    } catch (e) {
      console.error('WS parse error', e)
    }
  }
}

// =============== TASK ACTIONS ===============
const cancelTask = async () => {
  if (!taskId.value) return
  try {
    await fetch(buildApiUrl(`/tasks/${taskId.value}/cancel`), { method: 'POST' })
    status.value.state = 'REVOKED'
    status.value.message = '已取消'
    if (socket.value) socket.value.close()
  } catch (e) {
    errorMessage.value = normalizeErrorMessage(e)
  }
}

const downloadResults = () => {
  window.location.href = buildApiUrl(`/download/${taskId.value}`)
}

// =============== LIFECYCLE ===============
onBeforeUnmount(() => {
  if (socket.value) socket.value.close()
})
</script>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 48px 24px 64px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  animation: fadeIn 0.6s ease-out;
}

.header {
  animation: fadeInUp 0.5s ease-out;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr);
  gap: 28px;
  align-items: center;
}

.hero-text h1 {
  font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
  font-size: clamp(2rem, 4vw, 3.25rem);
  margin: 0 0 12px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-weight: 600;
  font-size: 0.8rem;
  color: var(--accent-1);
  margin: 0 0 12px;
}

.lead {
  margin: 0;
  color: var(--ink-2);
  font-size: 1.05rem;
  line-height: 1.7;
}

.panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

/* Animations */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .panel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 24px 16px 32px;
  }
}
</style>
