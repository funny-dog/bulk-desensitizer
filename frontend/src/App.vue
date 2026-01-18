<template>
  <div class="page">
    <header class="hero">
      <div class="hero-text">
        <p class="eyebrow">Bulk Data Processor</p>
        <h1>Async CSV/XLSX pipeline, real-time feedback.</h1>
        <p class="lead">
          Upload a large CSV and let FastAPI + Celery handle the heavy lifting while you
          watch progress tick upward.
        </p>
      </div>
      <div class="hero-card">
        <div>
          <p class="hero-label">Stack</p>
          <p class="hero-value">FastAPI · Celery · Redis · PostgreSQL</p>
        </div>
        <div>
          <p class="hero-label">Mode</p>
          <p class="hero-value">Non-blocking upload + async worker</p>
        </div>
        <div>
          <p class="hero-label">Cadence</p>
          <p class="hero-value">Status polling every 2 seconds</p>
        </div>
      </div>
    </header>

    <section class="panel">
      <div class="panel-card">
        <p class="panel-title">Upload CSV/XLSX</p>
        <label class="file-input">
          <input
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            @change="handleFile"
          />
          <span>Choose file</span>
        </label>
        <div class="file-meta">
          <p v-if="fileName" class="file-name">{{ fileName }}</p>
          <p v-else class="file-hint">Drop a CSV/XLSX here or click to select.</p>
        </div>
        <button class="primary" :disabled="!selectedFile || uploading" @click="uploadFile">
          {{ uploading ? 'Uploading...' : 'Upload & process' }}
        </button>
      </div>

      <div class="panel-card status">
        <div class="status-header">
          <div>
            <p class="panel-title">Task status</p>
            <p class="status-state">{{ statusLabel }}</p>
          </div>
          <div class="status-actions">
            <p v-if="taskId" class="task-id">{{ taskId }}</p>
            <div class="button-group">
              <button
                v-if="['PENDING', 'PROGRESS'].includes(status.state)"
                @click="cancelTask"
                class="cancel-btn"
              >
                Cancel
              </button>
              <button v-if="status.state === 'SUCCESS'" @click="downloadResults" class="download-btn">
                Download CSV
              </button>
            </div>
          </div>
        </div>

        <div class="progress-track">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>

        <div class="status-meta">
          <span>{{ progress }}%</span>
          <span v-if="status.total">{{ status.current }}/{{ status.total }}</span>
          <span v-if="status.message">{{ status.message }}</span>
        </div>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const selectedFile = ref(null)
const fileName = ref('')
const uploading = ref(false)
const taskId = ref('')
const errorMessage = ref('')
const status = ref({
  state: 'IDLE',
  current: 0,
  total: 0,
  message: ''
})

const socket = ref(null)

const progress = computed(() => {
  if (!status.value.total) {
    return 0
  }
  const ratio = status.value.current / status.value.total
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
})

const statusLabel = computed(() => {
  if (status.value.state === 'IDLE') return 'Waiting for upload'
  if (status.value.state === 'PENDING') return 'Queued'
  if (status.value.state === 'PROGRESS') return 'Processing'
  if (status.value.state === 'SUCCESS') return 'Completed'
  if (status.value.state === 'FAILURE') return 'Failed'
  return status.value.state
})

const handleFile = (event) => {
  const file = event.target.files?.[0] || null
  selectedFile.value = file
  fileName.value = file ? file.name : ''
}

const uploadFile = async () => {
  if (!selectedFile.value) {
    errorMessage.value = 'Please choose a CSV or XLSX file first.'
    return
  }

  errorMessage.value = ''
  uploading.value = true

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const response = await fetch(`${apiBase}/upload`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || 'Upload failed')
    }

    const data = await response.json()
    taskId.value = data.task_id
    status.value = {
      state: 'PENDING',
      current: 0,
      total: 0,
      message: 'queued'
    }

    connectWebSocket()
  } catch (error) {
    errorMessage.value = error?.message || 'Unexpected error'
  } finally {
    uploading.value = false
  }
}

const connectWebSocket = () => {
  if (socket.value) {
    socket.value.close()
  }

  const wsBase = apiBase.replace(/^http/, 'ws')
  socket.value = new WebSocket(`${wsBase}/ws/status/${taskId.value}`)

  socket.value.onopen = () => {
    console.log('WS Connected')
  }

  socket.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      status.value.current = data.current
      status.value.total = data.total
      status.value.message = data.message

      if (data.message === 'completed') {
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

const cancelTask = async () => {
  if (!taskId.value) return
  try {
    await fetch(`${apiBase}/tasks/${taskId.value}/cancel`, { method: 'POST' })
    status.value.state = 'REVOKED'
    status.value.message = 'Cancelled by user'
    if (socket.value) socket.value.close()
  } catch (e) {
    errorMessage.value = 'Failed to cancel task'
  }
}

const downloadResults = () => {
  window.location.href = `${apiBase}/export?task_id=${taskId.value}`
}

onBeforeUnmount(() => {
  if (socket.value) socket.value.close()
})
</script>

<style scoped>
.download-btn {
  background: white;
  border: 1px solid var(--stroke);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 600;
  color: var(--accent-1);
  transition: all 0.2s;
  margin-left: auto;
}
.download-btn:hover {
  background: var(--accent-1);
  color: white;
  border-color: var(--accent-1);
}

.cancel-btn {
  background: white;
  border: 1px solid #ef4444;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 600;
  color: #ef4444;
  transition: all 0.2s;
}

.cancel-btn:hover {
  background: #ef4444;
  color: white;
}

.button-group {
  display: flex;
  gap: 8px;
}

.status-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 48px 24px 64px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  animation: fadeIn 0.6s ease-out;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
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

.hero-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--stroke);
  border-radius: 20px;
  padding: 22px;
  display: grid;
  gap: 16px;
  box-shadow: var(--shadow);
}

.hero-label {
  margin: 0 0 6px;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ink-2);
}

.hero-value {
  margin: 0;
  font-weight: 600;
  font-size: 1rem;
}

.panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.panel-card {
  background: var(--card);
  border-radius: 20px;
  padding: 24px;
  border: 1px solid var(--stroke);
  box-shadow: 0 20px 40px rgba(31, 42, 48, 0.08);
  display: grid;
  gap: 16px;
}

.panel-title {
  margin: 0;
  font-weight: 600;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-2);
}

.file-input {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-radius: 999px;
  border: 1px dashed rgba(31, 42, 48, 0.3);
  background: rgba(15, 118, 110, 0.08);
  cursor: pointer;
  width: fit-content;
}

.file-input input {
  display: none;
}

.file-input span {
  font-weight: 600;
  color: var(--accent-1);
}

.file-meta {
  color: var(--ink-2);
}

.file-name {
  margin: 0;
  font-weight: 600;
}

.file-hint {
  margin: 0;
}

.primary {
  border: none;
  border-radius: 12px;
  padding: 12px 18px;
  font-weight: 600;
  background: linear-gradient(120deg, var(--accent-1), var(--accent-3));
  color: white;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.primary:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(15, 118, 110, 0.25);
}

.status {
  display: grid;
  gap: 18px;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
}

.status-state {
  margin: 6px 0 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.task-id {
  margin: 0;
  font-size: 0.85rem;
  color: var(--ink-2);
}

.progress-track {
  height: 14px;
  background: rgba(31, 42, 48, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-2), var(--accent-1));
  transition: width 0.4s ease;
}

.status-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: var(--ink-2);
  font-size: 0.95rem;
}

.error {
  margin: 0;
  color: #b91c1c;
  font-weight: 600;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .panel {
    grid-template-columns: 1fr;
  }
}
</style>
