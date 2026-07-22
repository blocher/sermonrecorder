<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CalendarDays,
  ChevronRight,
  Clock3,
  ListFilter,
  MapPin,
  Mic,
  Search,
  UserRound,
  X,
} from '@lucide/vue'
import { useAuth } from '../auth/useAuth'
import LocalDraftCard from '../components/LocalDraftCard.vue'
import ServerSermonCard from '../components/ServerSermonCard.vue'
import { useDraftRecorder } from '../recording/useDraftRecorder'
import {
  loadChurches,
  loadPreachers,
  deleteInProgressSermon,
  retrySermonProcessing,
  searchServerSermons,
  serverSermonDuration,
  serverSermonTitle,
  type OccasionKind,
  type ServerChurch,
  type ServerPreacher,
  type ServerSermon,
} from '../sermons/serverSermon'
import { useServerSermons } from '../sermons/useServerSermons'

const route = useRoute()
const router = useRouter()
const searchInput = ref<HTMLInputElement>()
const query = ref('')
const filterPanelOpen = ref(false)
const churchFilter = ref('')
const preacherFilter = ref('')
const occasionFilter = ref<OccasionKind | ''>('')
const tagFilter = ref('')
const dateFromFilter = ref('')
const dateToFilter = ref('')
const churches = ref<ServerChurch[]>([])
const preachers = ref<ServerPreacher[]>([])
const draftActionMessage = ref('')
const retryingSermons = ref<Record<string, boolean>>({})
const deletingSermons = ref<Record<string, boolean>>({})
const { isAuthenticated } = useAuth()
const { drafts, removeDraft, openDraftWizard } = useDraftRecorder()
const {
  pendingSermons,
  errorMessage: serverError,
  refresh: refreshServerSermons,
  startPolling,
  stopPolling,
} = useServerSermons()

const occasionOptions: { value: OccasionKind; label: string }[] = [
  { value: 'sunday', label: 'Sunday' },
  { value: 'feast', label: 'Feast or holy day' },
  { value: 'wedding', label: 'Wedding' },
  { value: 'funeral', label: 'Funeral' },
  { value: 'midweek', label: 'Midweek service' },
  { value: 'other', label: 'Other occasion' },
]

const readySermons = ref<ServerSermon[]>([])
const readyCount = ref(0)
const readyPage = ref(0)
const readyHasMore = ref(false)
const loadingReady = ref(false)
const searchResults = ref<ServerSermon[] | null>(null)
const searchCount = ref(0)
const searchPage = ref(0)
const searchHasMore = ref(false)
const searching = ref(false)
const searchError = ref('')
const loadingMore = ref(false)

const hasSearchCriteria = computed(
  () =>
    Boolean(query.value.trim()) ||
    Boolean(churchFilter.value) ||
    Boolean(preacherFilter.value) ||
    Boolean(occasionFilter.value) ||
    Boolean(tagFilter.value.trim()) ||
    Boolean(dateFromFilter.value) ||
    Boolean(dateToFilter.value),
)
const activeFilterCount = computed(
  () =>
    [
      churchFilter.value,
      preacherFilter.value,
      occasionFilter.value,
      tagFilter.value.trim(),
      dateFromFilter.value,
      dateToFilter.value,
    ].filter(Boolean).length,
)
const visibleSermons = computed(() => {
  if (!hasSearchCriteria.value) return readySermons.value
  return searchResults.value ?? []
})
const visibleCount = computed(() =>
  hasSearchCriteria.value ? searchCount.value : readyCount.value,
)
const hasMoreSermons = computed(() =>
  hasSearchCriteria.value ? searchHasMore.value : readyHasMore.value,
)
let searchTimer: ReturnType<typeof globalThis.setTimeout> | undefined
let searchVersion = 0

async function loadReadySermons(reset: boolean): Promise<void> {
  if (!isAuthenticated.value) {
    readySermons.value = []
    readyCount.value = 0
    readyPage.value = 0
    readyHasMore.value = false
    return
  }

  const page = reset ? 1 : readyPage.value + 1
  if (reset) loadingReady.value = true
  else loadingMore.value = true

  try {
    const result = await searchServerSermons({}, page)
    readySermons.value = reset ? result.results : [...readySermons.value, ...result.results]
    readyCount.value = result.count
    readyPage.value = page
    readyHasMore.value = Boolean(result.next)
  } catch (error) {
    if (reset) {
      readySermons.value = []
      readyCount.value = 0
      readyHasMore.value = false
    }
    searchError.value =
      error instanceof Error ? error.message : 'Your Sermon library could not be searched.'
  } finally {
    loadingReady.value = false
    loadingMore.value = false
  }
}

async function loadSearchBooks(): Promise<void> {
  if (!isAuthenticated.value) {
    churches.value = []
    preachers.value = []
    return
  }
  try {
    const [loadedChurches, loadedPreachers] = await Promise.all([
      loadChurches(),
      loadPreachers(),
    ])
    churches.value = loadedChurches
    preachers.value = loadedPreachers
  } catch {
    churches.value = []
    preachers.value = []
  }
}

function scheduleSearch(): void {
  searchVersion += 1
  const version = searchVersion
  if (searchTimer) globalThis.clearTimeout(searchTimer)
  searchResults.value = null
  searchCount.value = 0
  searchPage.value = 0
  searchHasMore.value = false
  searchError.value = ''

  if (!hasSearchCriteria.value || !isAuthenticated.value) {
    searching.value = false
    return
  }

  searching.value = true
  searchTimer = globalThis.setTimeout(() => void runSearch(version, true), 250)
}

async function runSearch(version: number, reset: boolean): Promise<void> {
  const page = reset ? 1 : searchPage.value + 1
  if (!reset) loadingMore.value = true

  try {
    const result = await searchServerSermons(
      {
        search: query.value,
        church: churchFilter.value,
        preacher: preacherFilter.value,
        occasion: occasionFilter.value,
        tag: tagFilter.value,
        date_from: dateFromFilter.value,
        date_to: dateToFilter.value,
      },
      page,
    )
    if (version !== searchVersion) return
    searchResults.value = reset ? result.results : [...(searchResults.value ?? []), ...result.results]
    searchCount.value = result.count
    searchPage.value = page
    searchHasMore.value = Boolean(result.next)
  } catch (error) {
    if (version !== searchVersion) return
    searchError.value =
      error instanceof Error ? error.message : 'Your Sermon library could not be searched.'
  } finally {
    if (version === searchVersion) {
      searching.value = false
      loadingMore.value = false
    }
  }
}

async function loadMoreSermons(): Promise<void> {
  if (loadingMore.value || searching.value || loadingReady.value || !hasMoreSermons.value) return
  if (hasSearchCriteria.value) {
    await runSearch(searchVersion, false)
    return
  }
  await loadReadySermons(false)
}

function clearSearch(): void {
  query.value = ''
  churchFilter.value = ''
  preacherFilter.value = ''
  occasionFilter.value = ''
  tagFilter.value = ''
  dateFromFilter.value = ''
  dateToFilter.value = ''
}

function capturedDate(sermon: ServerSermon): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(sermon.captured_at))
}

function announceDraftAction(message: string): void {
  draftActionMessage.value = message
  window.setTimeout(() => {
    draftActionMessage.value = ''
  }, 3000)
}

async function continueLocalDraft(id: string): Promise<void> {
  openDraftWizard(id)
}

async function removeLocalDraft(id: string): Promise<void> {
  try {
    await removeDraft(id)
    announceDraftAction('Draft deleted from this device.')
  } catch {
    announceDraftAction('The Draft could not be deleted. Try again.')
  }
}

async function retryFailedSermon(id: string): Promise<void> {
  retryingSermons.value = { ...retryingSermons.value, [id]: true }
  try {
    await retrySermonProcessing(id)
    await refreshServerSermons()
    announceDraftAction('Processing started again. Pewcorder will alert you when ready.')
  } catch (error) {
    announceDraftAction(
      error instanceof Error ? error.message : 'This Sermon could not be retried.',
    )
  } finally {
    const remaining = { ...retryingSermons.value }
    delete remaining[id]
    retryingSermons.value = remaining
  }
}

async function deleteInProgressServerSermon(id: string): Promise<void> {
  deletingSermons.value = { ...deletingSermons.value, [id]: true }
  try {
    await deleteInProgressSermon(id)
    await refreshServerSermons()
    announceDraftAction('Sermon deleted from the server.')
  } catch (error) {
    announceDraftAction(
      error instanceof Error ? error.message : 'This Sermon could not be deleted.',
    )
  } finally {
    const remaining = { ...deletingSermons.value }
    delete remaining[id]
    deletingSermons.value = remaining
  }
}

onMounted(() => void startPolling())
onBeforeUnmount(() => {
  stopPolling()
  searchVersion += 1
  if (searchTimer) globalThis.clearTimeout(searchTimer)
  document.body.classList.remove('library-search-lock')
})

watch(
  [
    query,
    churchFilter,
    preacherFilter,
    occasionFilter,
    tagFilter,
    dateFromFilter,
    dateToFilter,
  ],
  scheduleSearch,
)

watch(
  isAuthenticated,
  () => {
    void loadSearchBooks()
    scheduleSearch()
    void loadReadySermons(true)
  },
  { immediate: true },
)

watch(
  () => pendingSermons.value.map((sermon) => sermon.id).join(','),
  (ids, previous) => {
    if (previous === undefined || ids === previous) return
    void loadReadySermons(true)
  },
)

const searchOpen = computed(() => route.query.focus === 'search')

async function openSearch(): Promise<void> {
  if (searchOpen.value) {
    await nextTick()
    searchInput.value?.focus()
    return
  }
  await router.push({ query: { ...route.query, focus: 'search' } })
}

async function closeSearch(): Promise<void> {
  if (!searchOpen.value) return
  const nextQuery = { ...route.query }
  delete nextQuery.focus
  await router.replace({ query: nextQuery })
}

function clearSearchAndClose(): void {
  clearSearch()
  void closeSearch()
}

watch(
  searchOpen,
  async (open) => {
    document.body.classList.toggle('library-search-lock', open)
    if (!open) return
    await nextTick()
    searchInput.value?.focus()
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
          <p>Listen again, or search what was said.</p>
        </div>
        <span class="library__count">{{ readyCount }} sermons</span>
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
        @delete="removeLocalDraft"
        @continue="continueLocalDraft"
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
        :retrying="Boolean(retryingSermons[serverSermon.id])"
        :deleting="Boolean(deletingSermons[serverSermon.id])"
        @retry="retryFailedSermon"
        @delete="deleteInProgressServerSermon"
      />
    </section>

    <p v-if="serverError && isAuthenticated" class="server-error" role="status">
      {{ serverError }}
    </p>

    <div v-if="hasSearchCriteria && !searchOpen" class="library__filter-banner">
      <div>
        <p class="rubric-label">Filtered library</p>
        <span
          >{{ visibleCount }} matching {{ visibleCount === 1 ? 'sermon' : 'sermons' }}</span
        >
      </div>
      <div class="library__filter-banner-actions">
        <button type="button" @click="openSearch">Edit search</button>
        <button type="button" @click="clearSearch">Clear</button>
      </div>
    </div>

    <p v-if="searchError && !searchOpen" class="server-error" role="status">{{ searchError }}</p>

    <section aria-labelledby="recent-sermons">
      <div class="section-heading">
        <h2 id="recent-sermons">{{ hasSearchCriteria ? 'Search results' : 'Recently heard' }}</h2>
        <span v-if="searching || loadingReady">Loading…</span>
        <span v-else-if="visibleCount > visibleSermons.length"
          >{{ visibleSermons.length }} of {{ visibleCount }}</span
        >
        <span v-else
          >{{ visibleCount }} {{ visibleCount === 1 ? 'sermon' : 'sermons' }}</span
        >
      </div>

      <template v-if="!searching && !loadingReady && visibleSermons.length">
        <div class="sermon-list">
          <RouterLink
            v-for="(sermon, index) in visibleSermons"
            :key="sermon.id"
            class="sermon-entry"
            :to="`/sermons/${sermon.id}`"
          >
            <span class="sermon-entry__folio">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="sermon-entry__body">
              <div class="sermon-entry__rubric">
                <span>{{ sermon.liturgical_day || sermon.occasion_kind || 'Pew recording' }}</span>
                <span class="sermon-entry__ready">Ready</span>
              </div>
              <h3>{{ serverSermonTitle(sermon) }}</h3>
              <p class="sermon-entry__excerpt">
                {{ sermon.short_summary || 'Ready to revisit.' }}
              </p>
              <div class="sermon-entry__meta">
                <span v-if="sermon.preacher">
                  <UserRound :size="14" aria-hidden="true" />{{ sermon.preacher.name }}
                </span>
                <span v-if="sermon.church">
                  <MapPin :size="14" aria-hidden="true" />{{ sermon.church.name }}
                </span>
                <span>
                  <CalendarDays :size="14" aria-hidden="true" />{{ capturedDate(sermon) }}
                </span>
                <span>
                  <Clock3 :size="14" aria-hidden="true" />{{
                    serverSermonDuration(sermon.duration_seconds)
                  }}
                </span>
              </div>
              <div class="sermon-entry__tags">
                <span v-for="tag in sermon.tag_suggestions" :key="tag">{{ tag }}</span>
              </div>
            </div>
            <ChevronRight class="sermon-entry__arrow" :size="21" :stroke-width="1.6" aria-hidden="true" />
          </RouterLink>
        </div>

        <button
          v-if="hasMoreSermons"
          class="library__load-more"
          type="button"
          :disabled="loadingMore"
          @click="loadMoreSermons"
        >
          {{ loadingMore ? 'Loading…' : 'Show older sermons' }}
        </button>
      </template>

      <div v-else-if="!searching && !loadingReady" class="empty-search">
        <p class="rubric-label">{{ hasSearchCriteria ? 'No match' : 'Your library is ready' }}</p>
        <h3>
          {{
            hasSearchCriteria
              ? 'Nothing in your library matches this search yet.'
              : 'Your first processed Sermon will appear here.'
          }}
        </h3>
        <button v-if="hasSearchCriteria" type="button" @click="clearSearch">Clear search</button>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="searchOpen"
        class="library-search-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="library-search-title"
        @click.self="closeSearch"
      >
        <div class="library-search-overlay__panel">
          <header class="library-search-overlay__header">
            <div>
              <p id="library-search-title" class="rubric-label">Search library</p>
              <h2>Find what was said.</h2>
            </div>
            <button type="button" class="library-search-overlay__close" @click="closeSearch">
              Done
            </button>
          </header>

          <section
            class="library__search"
            :class="{ 'library__search--filters-open': filterPanelOpen }"
            aria-label="Search sermons"
          >
            <Search :size="20" :stroke-width="1.6" aria-hidden="true" />
            <input
              ref="searchInput"
              v-model="query"
              type="search"
              placeholder="Search transcripts, notes, Scripture…"
              aria-label="Search your sermons"
            />
            <button
              class="library__filter-toggle"
              type="button"
              :aria-expanded="filterPanelOpen"
              aria-controls="library-filters"
              @click="filterPanelOpen = !filterPanelOpen"
            >
              <ListFilter :size="17" aria-hidden="true" />
              Refine
              <span v-if="activeFilterCount">{{ activeFilterCount }}</span>
            </button>
          </section>

          <section
            v-if="filterPanelOpen"
            id="library-filters"
            class="library-filters"
            aria-label="Refine Sermon search"
          >
            <label>
              <span>Church</span>
              <select v-model="churchFilter">
                <option value="">Any Church</option>
                <option v-for="church in churches" :key="church.id" :value="church.id">
                  {{ church.name }}
                </option>
              </select>
            </label>
            <label>
              <span>Preacher</span>
              <select v-model="preacherFilter">
                <option value="">Any Preacher</option>
                <option v-for="preacher in preachers" :key="preacher.id" :value="preacher.id">
                  {{ preacher.name }}
                </option>
              </select>
            </label>
            <label>
              <span>Occasion</span>
              <select v-model="occasionFilter">
                <option value="">Any occasion</option>
                <option
                  v-for="occasion in occasionOptions"
                  :key="occasion.value"
                  :value="occasion.value"
                >
                  {{ occasion.label }}
                </option>
              </select>
            </label>
            <label>
              <span>Tag</span>
              <input v-model="tagFilter" type="search" placeholder="e.g. Grace" />
            </label>
            <label>
              <span>Heard after</span>
              <input v-model="dateFromFilter" type="date" />
            </label>
            <label>
              <span>Heard before</span>
              <input v-model="dateToFilter" type="date" />
            </label>
            <button v-if="activeFilterCount || query.trim()" type="button" @click="clearSearch">
              <X :size="15" aria-hidden="true" />
              Clear all
            </button>
          </section>

          <p v-if="searchError" class="server-error" role="status">{{ searchError }}</p>

          <div class="library-search-overlay__results">
            <div class="section-heading">
              <h3>{{ hasSearchCriteria ? 'Matching sermons' : 'Ready sermons' }}</h3>
              <span v-if="searching || loadingReady">Loading…</span>
              <span v-else-if="visibleCount > visibleSermons.length"
                >{{ visibleSermons.length }} of {{ visibleCount }}</span
              >
              <span v-else
                >{{ visibleCount }} {{ visibleCount === 1 ? 'sermon' : 'sermons' }}</span
              >
            </div>

            <template v-if="!searching && !loadingReady && visibleSermons.length">
              <div class="sermon-list">
                <RouterLink
                  v-for="(sermon, index) in visibleSermons"
                  :key="sermon.id"
                  class="sermon-entry"
                  :to="`/sermons/${sermon.id}`"
                  @click="closeSearch"
                >
                  <span class="sermon-entry__folio">{{ String(index + 1).padStart(2, '0') }}</span>
                  <div class="sermon-entry__body">
                    <div class="sermon-entry__rubric">
                      <span>{{
                        sermon.liturgical_day || sermon.occasion_kind || 'Pew recording'
                      }}</span>
                      <span class="sermon-entry__ready">Ready</span>
                    </div>
                    <h3>{{ serverSermonTitle(sermon) }}</h3>
                    <p class="sermon-entry__excerpt">
                      {{ sermon.short_summary || 'Ready to revisit.' }}
                    </p>
                  </div>
                  <ChevronRight
                    class="sermon-entry__arrow"
                    :size="21"
                    :stroke-width="1.6"
                    aria-hidden="true"
                  />
                </RouterLink>
              </div>

              <button
                v-if="hasMoreSermons"
                class="library__load-more"
                type="button"
                :disabled="loadingMore"
                @click="loadMoreSermons"
              >
                {{ loadingMore ? 'Loading…' : 'Show older sermons' }}
              </button>
            </template>

            <div v-else-if="!searching && !loadingReady" class="empty-search">
              <p class="rubric-label">{{ hasSearchCriteria ? 'No match' : 'Browse' }}</p>
              <h3>
                {{
                  hasSearchCriteria
                    ? 'Nothing in your library matches this search yet.'
                    : 'Type to filter your Ready sermons.'
                }}
              </h3>
              <button v-if="hasSearchCriteria" type="button" @click="clearSearchAndClose">
                Clear search
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.library {
  margin: 0 auto;
  max-width: 64rem;
  padding: 3rem clamp(1.25rem, 4vw, 3rem) 8rem;
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

.library__load-more {
  background: transparent;
  border: 1px solid var(--color-lapis);
  color: var(--color-lapis);
  cursor: pointer;
  display: block;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  margin: 1.5rem auto 0;
  min-height: 2.75rem;
  padding: 0.65rem 1.25rem;
  width: min(100%, 18rem);
}

.library__load-more:disabled {
  cursor: wait;
  opacity: 0.7;
}

.library__load-more:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: 3px;
}

.library__filter-banner {
  align-items: center;
  border: 1px solid var(--color-margin);
  border-left: 2px solid var(--color-lapis);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin: 0 0 1.75rem;
  padding: 0.9rem 1rem;
}

.library__filter-banner .rubric-label {
  margin-bottom: 0.2rem;
}

.library__filter-banner > div:first-child span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.78rem;
}

.library__filter-banner-actions {
  display: flex;
  gap: 0.75rem;
}

.library__filter-banner-actions button {
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.35rem 0.15rem;
  text-decoration: underline;
  text-underline-offset: 0.2rem;
}

.library-search-overlay {
  background: color-mix(in srgb, var(--color-ink) 28%, transparent);
  bottom: 0;
  left: 0;
  overflow: auto;
  padding: 0.75rem 0.75rem 1.5rem;
  position: fixed;
  right: 0;
  top: var(--header-height);
  z-index: 45;
}

.library-search-overlay__panel {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  box-shadow: 0 22px 60px rgba(28, 36, 48, 0.22);
  margin: 0 auto;
  max-width: 44rem;
  min-height: min(36rem, calc(100svh - var(--header-height) - 2rem));
  padding: 1.35rem clamp(1rem, 3vw, 1.75rem) 2rem;
}

.library-search-overlay__header {
  align-items: start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.library-search-overlay__header h2 {
  font-family: var(--font-display);
  font-size: clamp(1.7rem, 5vw, 2.4rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 40;
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1;
  margin: 0.35rem 0 0;
}

.library-search-overlay__close {
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  min-height: 2.5rem;
  padding: 0.55rem 1rem;
  text-transform: uppercase;
}

.library-search-overlay__close:focus-visible {
  outline: 2px solid var(--color-rule-gold);
  outline-offset: 3px;
}

.library-search-overlay .library__search {
  margin: 0 0 1rem;
}

.library-search-overlay .library-filters {
  margin-bottom: 1.25rem;
}

.library-search-overlay__results .section-heading {
  margin-bottom: 0.85rem;
}

.library-search-overlay__results .section-heading h3 {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 540;
  margin: 0;
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

.library__search--filters-open {
  margin-bottom: 0.75rem;
}

.library__filter-toggle {
  align-items: center;
  background: transparent;
  border: 0;
  border-left: 1px solid var(--color-margin);
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
  gap: 0.35rem;
  min-height: 2rem;
  padding: 0 0 0 0.9rem;
}

.library__filter-toggle span {
  align-items: center;
  background: var(--color-lapis);
  border-radius: 999px;
  color: var(--color-vellum-light);
  display: inline-flex;
  font-size: 0.65rem;
  height: 1.25rem;
  justify-content: center;
  min-width: 1.25rem;
  padding: 0 0.3rem;
}

.library-filters {
  background:
    linear-gradient(90deg, rgba(47, 75, 124, 0.05), transparent 42%),
    var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  border-left: 3px solid var(--color-lapis);
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0 0 3rem;
  padding: 1.25rem;
}

.library-filters label {
  display: grid;
  gap: 0.35rem;
}

.library-filters label > span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.67rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.library-filters input,
.library-filters select {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  border-radius: 0;
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  min-height: 2.65rem;
  padding: 0.45rem 0.55rem;
  width: 100%;
}

.library-filters input:focus,
.library-filters select:focus {
  border-color: var(--color-lapis);
  outline: 2px solid rgba(47, 75, 124, 0.12);
  outline-offset: 1px;
}

.library-filters > button {
  align-items: center;
  align-self: end;
  background: transparent;
  border: 0;
  color: var(--color-rubric);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.75rem;
  font-weight: 700;
  gap: 0.35rem;
  justify-self: start;
  min-height: 2.65rem;
  padding: 0;
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

  .library__search--filters-open {
    margin-bottom: 0.75rem;
  }

  .library__filter-toggle {
    font-size: 0;
    padding-left: 0.65rem;
  }

  .library__filter-toggle span {
    font-size: 0.65rem;
  }

  .library-filters {
    grid-template-columns: 1fr;
    margin-bottom: 2.25rem;
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
