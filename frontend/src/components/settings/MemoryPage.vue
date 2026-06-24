<template>
  <main class="chat-main">
    <header class="chat-header">
      <div class="chat-header-left">
        <button type="button" class="chat-icon-btn" aria-label="返回设置" @click="$emit('back')">
          <ArrowLeft :size="18" />
        </button>
        <span class="chat-header-title">记忆库</span>
      </div>
      <div class="chat-header-actions">
        <button type="button" class="chat-primary-btn" :disabled="loading" @click="loadMemory">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </header>

    <div
      v-if="showEmbeddingBanner"
      :class="['memory-embed-banner', embeddingBannerClass]"
      role="status"
      aria-live="polite"
    >
      <div class="memory-embed-header">
        <span class="memory-embed-title">嵌入模型</span>
        <span v-if="embeddingModel?.model" class="memory-embed-model">{{ embeddingModel.model }}</span>
      </div>
      <p class="memory-embed-message">{{ embeddingModel?.message }}</p>
      <p v-if="embeddingModel?.resumed && showProgressBar" class="memory-embed-resume-hint">
        检测到未完成的下载，将从断点续传
      </p>
      <div
        v-if="showProgressBar"
        class="memory-embed-progress"
        :aria-valuenow="progressValue"
        aria-valuemin="0"
        aria-valuemax="100"
        role="progressbar"
      >
        <div
          :class="['memory-embed-progress-bar', { indeterminate: isIndeterminateProgress }]"
          :style="progressBarStyle"
        />
      </div>
      <p v-if="embeddingModel?.status === 'missing_deps'" class="memory-embed-hint">
        请在后端环境执行：<code>pip install 'desktopclaw[memory]'</code>
      </p>
      <p v-else-if="embeddingModel?.status === 'failed' && embeddingModel?.error" class="memory-embed-error">
        {{ embeddingModel.error }}
      </p>
      <button
        v-if="embeddingModel?.status === 'failed'"
        type="button"
        class="chat-secondary-btn memory-embed-retry-btn"
        :disabled="retrying"
        @click="retryEmbedding"
      >
        {{ retrying ? '重试中…' : '重试下载' }}
      </button>
    </div>

    <div v-if="stats" class="memory-stats-bar">
      共 {{ stats.strategyCount }} 条 · 就绪 {{ stats.readyCount }} · 索引中 {{ stats.pendingCount }}
      <span v-if="stats.failedCount"> · 失败 {{ stats.failedCount }}</span>
    </div>

    <div class="memory-tabs">
      <button
        type="button"
        :class="['memory-tab', { active: activeTab === 'user' }]"
        @click="activeTab = 'user'"
      >
        用户记忆
      </button>
      <button
        type="button"
        :class="['memory-tab', { active: activeTab === 'strategy' }]"
        @click="activeTab = 'strategy'"
      >
        策略记忆
      </button>
    </div>

    <div class="memory-content">
      <div v-if="loading && !memory" class="memory-state">加载中...</div>
      <div v-else-if="error" class="memory-state memory-state-error">{{ error }}</div>

      <template v-else-if="activeTab === 'user'">
        <div
          v-if="userMarkdown"
          class="memory-markdown markdown-body"
          v-html="renderMarkdown(userMarkdown)"
        />
        <div v-else class="memory-empty">暂无长期记忆</div>
      </template>

      <template v-else>
        <div v-if="!strategies.length" class="memory-empty">暂无策略记忆</div>
        <div v-else class="memory-strategy-list">
          <article v-for="item in strategies" :key="item.id" class="memory-strategy-card">
            <div class="memory-strategy-header">
              <span :class="['memory-kind-badge', item.kind]">{{ kindLabel(item.kind) }}</span>
              <h3 class="memory-strategy-title">{{ item.title }}</h3>
            </div>
            <p v-if="item.description" class="memory-strategy-desc">{{ item.description }}</p>
            <details v-if="item.content" class="memory-strategy-content">
              <summary>详细内容</summary>
              <p>{{ item.content }}</p>
            </details>
            <div class="memory-strategy-meta">
              <span v-if="item.domain">领域：{{ item.domain }}</span>
              <span v-if="item.tools?.length">工具：{{ item.tools.join(', ') }}</span>
              <span v-if="item.confidence != null">置信度：{{ formatConfidence(item.confidence) }}</span>
              <span v-if="item.hitCount != null">命中：{{ item.hitCount }}</span>
              <span :class="['memory-index-status', item.indexStatus]">
                {{ indexStatusLabel(item) }}
              </span>
            </div>
            <p v-if="item.indexStatus === 'failed' && item.indexError" class="memory-index-error">
              {{ item.indexError }}
            </p>
          </article>
        </div>
      </template>
    </div>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ArrowLeft } from 'lucide-vue-next'
import { fetchMemory, retryEmbeddingDownload } from '../../api/memory.js'
import { renderMarkdown } from '../../utils/markdown.js'

defineEmits(['back'])

const POLL_INTERVAL_MS = 2000
const ACTIVE_EMBED_STATUSES = new Set(['pending', 'downloading', 'loading'])

const activeTab = ref('user')
const loading = ref(false)
const retrying = ref(false)
const error = ref('')
const memory = ref(null)
let pollTimer = null

const userMarkdown = computed(() => memory.value?.userMemory?.markdown || '')
const strategies = computed(() => memory.value?.strategies || [])
const stats = computed(() => memory.value?.stats || null)
const embeddingModel = computed(() => memory.value?.embeddingModel || null)

const showEmbeddingBanner = computed(() => {
  const status = embeddingModel.value?.status
  return status && status !== 'ready' && status !== 'disabled'
})

const embeddingBannerClass = computed(() => {
  const status = embeddingModel.value?.status
  if (status === 'failed') return 'is-failed'
  if (status === 'missing_deps') return 'is-warning'
  return 'is-active'
})

const showProgressBar = computed(() => {
  const status = embeddingModel.value?.status
  return status === 'pending' || status === 'downloading' || status === 'loading'
})

const isIndeterminateProgress = computed(() => {
  const status = embeddingModel.value?.status
  const progress = embeddingModel.value?.progress
  return status === 'pending' || status === 'loading' || progress == null
})

const progressValue = computed(() => {
  const progress = embeddingModel.value?.progress
  if (progress == null) return undefined
  return Math.round(progress)
})

const progressBarStyle = computed(() => {
  if (isIndeterminateProgress.value) return {}
  const progress = embeddingModel.value?.progress ?? 0
  return { width: `${Math.max(0, Math.min(100, progress))}%` }
})

function kindLabel(kind) {
  if (kind === 'pitfall') return '陷阱'
  return '策略'
}

function formatConfidence(value) {
  return `${Math.round(value * 100)}%`
}

function indexStatusLabel(item) {
  const status = item.indexStatus || 'pending'
  if (status === 'ready') return '已索引'
  if (status === 'failed') return '索引失败'
  return '索引中'
}

function shouldPoll(status) {
  return ACTIVE_EMBED_STATUSES.has(status)
}

function syncPollTimer() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  const status = embeddingModel.value?.status
  if (shouldPoll(status)) {
    pollTimer = setInterval(() => {
      loadMemory({ silent: true })
    }, POLL_INTERVAL_MS)
  }
}

async function retryEmbedding() {
  retrying.value = true
  try {
    const result = await retryEmbeddingDownload()
    if (memory.value) {
      memory.value = {
        ...memory.value,
        embeddingModel: result.embeddingModel || memory.value.embeddingModel,
      }
    }
    await loadMemory({ silent: true })
    syncPollTimer()
  } catch (e) {
    error.value = e?.message || '重试下载失败'
  } finally {
    retrying.value = false
  }
}

async function loadMemory(options = {}) {
  const silent = options.silent === true
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    memory.value = await fetchMemory()
  } catch (e) {
    if (!silent) {
      error.value = e?.message || '加载记忆失败'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

watch(embeddingModel, () => {
  syncPollTimer()
}, { deep: true })

onMounted(async () => {
  await loadMemory()
  syncPollTimer()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>
