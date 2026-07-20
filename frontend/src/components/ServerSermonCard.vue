<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, CloudUpload, LoaderCircle } from '@lucide/vue'
import type { ServerSermon } from '../sermons/useServerSermons'

const props = defineProps<{
  sermon: ServerSermon
}>()

const title = computed(() => {
  const captured = new Date(props.sermon.captured_at)
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(captured)
})

const details = computed(() => {
  const captured = new Date(props.sermon.captured_at)
  const time = new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(captured)
  const minutes = Math.max(1, Math.round(props.sermon.duration_seconds / 60))
  return `${time} · ${minutes} min`
})

const statusLabel = computed(() => {
  if (props.sermon.processing_status === 'processing') return 'Preparing'
  if (props.sermon.processing_status === 'failed') return 'Needs attention'
  return 'Safely uploaded'
})
</script>

<template>
  <article class="server-sermon" :class="`server-sermon--${sermon.processing_status}`">
    <span class="server-sermon__icon" aria-hidden="true">
      <LoaderCircle
        v-if="sermon.processing_status === 'processing'"
        class="server-sermon__spinner"
        :size="21"
      />
      <CircleAlert v-else-if="sermon.processing_status === 'failed'" :size="21" />
      <CloudUpload v-else :size="21" />
    </span>
    <div>
      <span class="server-sermon__status">{{ statusLabel }}</span>
      <strong>{{ title }} sermon</strong>
      <small>{{ details }}</small>
      <p>{{ sermon.processing_message }}</p>
    </div>
  </article>
</template>

<style scoped>
.server-sermon {
  align-items: start;
  background: color-mix(in srgb, var(--color-margin) 72%, var(--color-vellum-light));
  border-left: 2px solid var(--color-lapis);
  display: grid;
  gap: 0.9rem;
  grid-template-columns: auto 1fr;
  padding: 1rem 1.1rem;
}

.server-sermon + .server-sermon {
  border-top: 1px solid var(--color-vellum);
}

.server-sermon--failed {
  border-left-color: var(--color-rubric);
}

.server-sermon__icon {
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--color-lapis) 35%, transparent);
  border-radius: 50%;
  color: var(--color-lapis);
  display: flex;
  height: 2.65rem;
  justify-content: center;
  width: 2.65rem;
}

.server-sermon--failed .server-sermon__icon,
.server-sermon--failed .server-sermon__status {
  color: var(--color-rubric);
}

.server-sermon__status,
.server-sermon strong,
.server-sermon small {
  display: block;
  font-family: var(--font-utility);
}

.server-sermon__status {
  color: var(--color-lapis);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  margin-bottom: 0.15rem;
  text-transform: uppercase;
}

.server-sermon strong {
  font-size: 0.9rem;
  font-weight: 650;
}

.server-sermon small,
.server-sermon p {
  color: var(--color-ink-muted);
}

.server-sermon small {
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.server-sermon p {
  font-family: var(--font-reading);
  font-size: 0.78rem;
  line-height: 1.45;
  margin: 0.45rem 0 0;
}

.server-sermon__spinner {
  animation: server-spin 1s linear infinite;
}

@keyframes server-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .server-sermon__spinner {
    animation: none;
  }
}
</style>
