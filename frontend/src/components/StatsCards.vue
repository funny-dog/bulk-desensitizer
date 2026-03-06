<template>
  <div class="stats-cards">
    <div class="stat-card">
      <div class="stat-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
      </div>
      <div class="stat-content">
        <span class="stat-value">{{ filesProcessed }}</span>
        <span class="stat-label">Files Processed</span>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      </div>
      <div class="stat-content">
        <span class="stat-value">{{ successRate }}%</span>
        <span class="stat-label">Success Rate</span>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
      </div>
      <div class="stat-content">
        <span class="stat-value">{{ activeTasks }}</span>
        <span class="stat-label">Active Tasks</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const filesProcessed = ref(0)
const successRate = ref(100)
const activeTasks = ref(0)

// Simple count-up animation
const animateValue = (refValue, start, end, duration) => {
  const startTime = performance.now()
  const diff = end - start
  
  const update = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    // Ease out
    const easeProgress = 1 - Math.pow(1 - progress, 3)
    refValue.value = Math.round(start + diff * easeProgress)
    
    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }
  
  requestAnimationFrame(update)
}

onMounted(() => {
  // Staggered animation
  setTimeout(() => animateValue(filesProcessed, 0, 124, 800), 100)
  setTimeout(() => animateValue(successRate, 0, 100, 600), 200)
  setTimeout(() => animateValue(activeTasks, 0, 2, 500), 300)
})
</script>

<style scoped>
.stats-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  background: linear-gradient(135deg, var(--accent-1), var(--accent-3));
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  color: white;
  animation: fadeInUp 0.5s ease-out both;
}

.stat-card:nth-child(1) { animation-delay: 0s; }
.stat-card:nth-child(2) { animation-delay: 0.1s; }
.stat-card:nth-child(3) { animation-delay: 0.2s; }

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  font-family: 'Space Grotesk', sans-serif;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.85rem;
  opacity: 0.9;
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

@media (max-width: 640px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }
}
</style>
