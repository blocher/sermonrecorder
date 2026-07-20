<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CalendarDays, ChevronRight, Clock3, Mic, MapPin, Search } from '@lucide/vue'
import { useAuth } from '../auth/useAuth'
import LocalDraftCard from '../components/LocalDraftCard.vue'
import ServerSermonCard from '../components/ServerSermonCard.vue'
import { sermons } from '../data/sermons'
import { useDraftRecorder } from '../recording/useDraftRecorder'
import { useServerSermons } from '../sermons/useServerSermons'
import { uploadDraft } from '../upload/uploadDraft'

const route = useRoute()
const router = useRouter()
const searchInput = ref<HTMLInputElement>()
const query = ref('')
const draftActionMessage = ref('')
const uploadProgress = ref<Record<string, number>>({})
const { isAuthenticated } = useAuth()
const { drafts, removeDraft } = useDraftRecorder()
const {
  pendingSermons,
  errorMessage: serverError,
  refresh: refreshServerSermons,
  startPolling,
  stopPolling,
} = useServerSermons()

const visibleSermons = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return sermons

  return sermons.filter((sermon) => {
    const searchText = [
      sermon.title,
      sermon.preacher,
      sermon.church,
      sermon.occasion,
      sermon.liturgicalDay,
      sermon.tags.join(' '),
      sermon.scripture.join(' '),
      sermon.shortSummary,
    ]
      .join(' ')
      .toLowerCase()

    return searchText.includes(needle)
  })
})

function announceDraftAction(message: string): void {
  draftActionMessage.value = message
  window.setTimeout(() => {
    draftActionMessage.value = ''
  }, 3000)
}

async function removeLocalDraft(id: string): Promise<void> {
  try {
    await removeDraft(id)
    announceDraftAction('Draft deleted from this device.')
  } catch {
    announceDraftAction('The Draft could not be deleted. Try again.')
  }
}

async function uploadLocalDraft(id: string): Promise<void> {
  const draft = drafts.value.find((candidate) => candidate.id === id)
  if (!draft) return

  if (!isAuthenticated.value) {
    await router.push({ name: 'account', query: { redirect: '/' } })
    return
  }

  uploadProgress.value = { ...uploadProgress.value, [id]: 0 }
  announceDraftAction('Uploading this Draft securely…')

  try {
    await uploadDraft(draft, (progress) => {
      uploadProgress.value = { ...uploadProgress.value, [id]: progress }
    })
    await removeDraft(id)
    await refreshServerSermons()
    announceDraftAction('Draft uploaded. Pewcorder will alert you when the Sermon is ready.')
  } catch (error) {
    announceDraftAction(error instanceof Error ? error.message : 'The Draft could not be uploaded.')
  } finally {
    const remaining = { ...uploadProgress.value }
    delete remaining[id]
    uploadProgress.value = remaining
  }
}

onMounted(() => void startPolling())
onBeforeUnmount(stopPolling)

watch(
  () => route.query.focus,
  async (focus) => {
    if (focus === 'search') {
      await nextTick()
      searchInput.value?.focus()
    }
  },
  { immediate: true },
)
</script>

<template>
  <main class="library page-gather">
    <section class="library__heading">
      <p class="rubric-label">Your library</p>
      <div class="library__title-row">
        <div>
          <h1>Sermons worth returning to.</h1>
          <p>Listen again, search what was said, or continue a reflection.</p>
        </div>
        <span class="library__count">{{ sermons.length }} sermons</span>
      </div>
    </section>

    <section v-if="drafts.length" class="drafts" aria-labelledby="local-drafts">
      <div class="drafts__heading">
        <p id="local-drafts" class="rubric-label">Waiting to upload</p>
        <span>{{ drafts.length }} on this device</span>
      </div>
      <LocalDraftCard
        v-for="draft in drafts"
        :key="draft.id"
        :draft="draft"
        :uploading="draft.id in uploadProgress"
        :upload-progress="uploadProgress[draft.id]"
        @delete="removeLocalDraft"
        @upload="uploadLocalDraft"
      />
    </section>

    <aside v-else class="draft-empty">
      <Mic :size="20" :stroke-width="1.6" aria-hidden="true" />
      <span>
        <strong>No local Drafts</strong>
        <small>The Record seal works from anywhere, even before you sign in.</small>
      </span>
    </aside>

    <p v-if="draftActionMessage" class="draft-action-message" role="status">
      {{ draftActionMessage }}
    </p>

    <section
      v-if="pendingSermons.length"
      class="drafts server-sermons"
      aria-labelledby="preparing-sermons"
    >
      <div class="drafts__heading">
        <p id="preparing-sermons" class="rubric-label">In preparation</p>
        <span>{{ pendingSermons.length }} on the server</span>
      </div>
      <ServerSermonCard
        v-for="serverSermon in pendingSermons"
        :key="serverSermon.id"
        :sermon="serverSermon"
      />
    </section>

    <p v-if="serverError && isAuthenticated" class="server-error" role="status">
      {{ serverError }}
    </p>

    <section class="library__search" aria-label="Search sermons">
      <Search :size="20" :stroke-width="1.6" aria-hidden="true" />
      <input
        ref="searchInput"
        v-model="query"
        type="search"
        placeholder="Search words, Scripture, preachers…"
        aria-label="Search your sermons"
      />
      <kbd>⌘ K</kbd>
    </section>

    <section aria-labelledby="recent-sermons">
      <div class="section-heading">
        <h2 id="recent-sermons">{{ query ? 'Search results' : 'Recently heard' }}</h2>
        <span>{{ visibleSermons.length }} {{ visibleSermons.length === 1 ? 'sermon' : 'sermons' }}</span>
      </div>

      <div v-if="visibleSermons.length" class="sermon-list">
        <RouterLink
          v-for="(sermon, index) in visibleSermons"
          :key="sermon.id"
          class="sermon-entry"
          :to="`/sermons/${sermon.id}`"
        >
          <span class="sermon-entry__folio">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="sermon-entry__body">
            <div class="sermon-entry__rubric">
              <span>{{ sermon.liturgicalDay }}</span>
              <span class="sermon-entry__ready">Ready</span>
            </div>
            <h3>{{ sermon.title }}</h3>
            <p class="sermon-entry__excerpt">{{ sermon.excerpt }}</p>
            <div class="sermon-entry__meta">
              <span>{{ sermon.preacher }}</span>
              <span><MapPin :size="14" aria-hidden="true" />{{ sermon.church }}</span>
              <span><CalendarDays :size="14" aria-hidden="true" />{{ sermon.date }}</span>
              <span><Clock3 :size="14" aria-hidden="true" />{{ sermon.duration }}</span>
            </div>
            <div class="sermon-entry__tags">
              <span v-for="tag in sermon.tags" :key="tag">{{ tag }}</span>
            </div>
          </div>
          <ChevronRight class="sermon-entry__arrow" :size="21" :stroke-width="1.6" aria-hidden="true" />
        </RouterLink>
      </div>

      <div v-else class="empty-search">
        <p class="rubric-label">No match</p>
        <h3>Nothing in your library uses “{{ query }}” yet.</h3>
        <button type="button" @click="query = ''">Clear search</button>
      </div>
    </section>
  </main>
</template>

<style scoped>
.library {
  margin: 0 auto;
  max-width: 64rem;
  padding: 3rem clamp(1.25rem, 4vw, 3rem) 9rem;
}

.library__heading {
  border-bottom: 1px solid var(--color-rule-gold);
  padding-bottom: 2rem;
}

.library__title-row {
  align-items: end;
  display: flex;
  gap: 2rem;
  justify-content: space-between;
}

.library__title-row h1 {
  font-family: var(--font-display);
  font-size: clamp(2.35rem, 6vw, 4.4rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 48, 'WONK' 0;
  font-weight: 520;
  letter-spacing: -0.055em;
  line-height: 0.98;
  margin: 0.55rem 0 0.9rem;
  max-width: 13ch;
}

.library__title-row p {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 1.02rem;
  line-height: 1.55;
}

.library__count {
  color: var(--color-ink-muted);
  flex: none;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.09em;
  padding-bottom: 0.3rem;
  text-transform: uppercase;
}

.drafts,
.draft-empty {
  margin: 1.5rem 0;
}

.drafts__heading {
  align-items: baseline;
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.55rem;
}

.drafts__heading > span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
}

.draft-empty {
  align-items: center;
  background: var(--color-margin);
  border-left: 2px solid var(--color-lapis);
  color: var(--color-lapis);
  display: grid;
  gap: 0.85rem;
  grid-template-columns: auto 1fr;
  padding: 1rem 1.15rem;
}

.draft-empty strong,
.draft-empty small {
  display: block;
  font-family: var(--font-utility);
}

.draft-empty strong {
  color: var(--color-ink);
  font-size: 0.9rem;
  font-weight: 650;
}

.draft-empty small {
  color: var(--color-ink-muted);
  font-size: 0.78rem;
  margin-top: 0.15rem;
}

.draft-action-message {
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  margin: -0.75rem 0 1.5rem;
}

.server-error {
  color: var(--color-rubric);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  margin: 1rem 0 1.5rem;
}

.empty-search button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.75rem;
  text-decoration: underline;
  text-underline-offset: 0.25rem;
}

.library__search {
  align-items: center;
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  display: grid;
  gap: 0.75rem;
  grid-template-columns: auto 1fr auto;
  margin: 1.5rem 0 3rem;
  padding: 0.4rem 1rem;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.library__search:focus-within {
  border-color: var(--color-lapis);
  box-shadow: 0 0 0 3px rgba(47, 75, 124, 0.12);
}

.library__search svg {
  color: var(--color-lapis);
}

.library__search input {
  background: transparent;
  border: 0;
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 1rem;
  min-height: 2.75rem;
  outline: 0;
  width: 100%;
}

.library__search input::placeholder {
  color: var(--color-ink-muted);
}

.library__search kbd {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  padding: 0.15rem 0.4rem;
}

.section-heading {
  align-items: baseline;
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.section-heading h2 {
  font-family: var(--font-display);
  font-size: 1.45rem;
  font-weight: 560;
  margin: 0;
}

.section-heading > span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.76rem;
}

.sermon-list {
  border-top: 1px solid var(--color-ink);
}

.sermon-entry {
  align-items: start;
  border-bottom: 1px solid var(--color-margin);
  color: inherit;
  display: grid;
  gap: 1.25rem;
  grid-template-columns: 2.5rem 1fr auto;
  padding: 1.75rem 0.75rem 1.75rem 0;
  text-decoration: none;
  transition:
    background-color 160ms ease,
    padding 160ms ease;
}

.sermon-entry:hover,
.sermon-entry:focus-visible {
  background: rgba(250, 248, 241, 0.76);
  padding-left: 0.75rem;
}

.sermon-entry:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 2px;
}

.sermon-entry__folio {
  color: var(--color-rubric);
  font-family: var(--font-display);
  font-size: 0.82rem;
  font-variant-numeric: oldstyle-nums;
  padding-top: 0.25rem;
  text-align: center;
}

.sermon-entry__rubric {
  align-items: center;
  color: var(--color-rubric);
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 680;
  gap: 0.75rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.sermon-entry__ready {
  color: var(--color-lapis);
}

.sermon-entry__rubric span + span::before {
  color: var(--color-rule-gold);
  content: '·';
  margin-right: 0.75rem;
}

.sermon-entry h3 {
  font-family: var(--font-display);
  font-size: clamp(1.55rem, 3vw, 2rem);
  font-variation-settings: 'opsz' 36, 'SOFT' 45;
  font-weight: 540;
  letter-spacing: -0.025em;
  line-height: 1.08;
  margin: 0.45rem 0 0.7rem;
}

.sermon-entry__excerpt {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.9rem;
  line-height: 1.55;
  max-width: 62ch;
}

.sermon-entry__meta {
  color: var(--color-ink-muted);
  display: flex;
  flex-wrap: wrap;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  gap: 0.5rem 1.1rem;
  margin-top: 1rem;
}

.sermon-entry__meta span {
  align-items: center;
  display: inline-flex;
  gap: 0.3rem;
}

.sermon-entry__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.sermon-entry__tags span {
  border-bottom: 1px solid rgba(47, 75, 124, 0.35);
  color: var(--color-lapis);
  font-family: var(--font-utility);
  font-size: 0.72rem;
  padding-bottom: 0.1rem;
}

.sermon-entry__arrow {
  align-self: center;
  color: var(--color-rule-gold);
}

.empty-search {
  border-bottom: 1px solid var(--color-margin);
  border-top: 1px solid var(--color-ink);
  padding: 3rem 0;
  text-align: center;
}

.empty-search h3 {
  font-family: var(--font-reading);
  font-size: 1.1rem;
  font-weight: 450;
}

@media (max-width: 680px) {
  .library {
    padding-top: 2rem;
  }

  .library__title-row {
    align-items: start;
    flex-direction: column;
    gap: 0.8rem;
  }

  .library__count {
    padding: 0;
  }

  .library__search {
    margin-bottom: 2.25rem;
  }

  .library__search kbd {
    display: none;
  }

  .sermon-entry {
    gap: 0.7rem;
    grid-template-columns: 1.8rem 1fr;
    padding-right: 0;
  }

  .sermon-entry__arrow {
    display: none;
  }

  .sermon-entry__excerpt {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}
</style>
