<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, Plus, Send } from '@lucide/vue'
import BrandMark from '../components/BrandMark.vue'
import { useAuth } from '../auth/useAuth'
import {
  createSavedRecipient,
  loadSavedRecipients,
  loadServerSermon,
  sendSermonEmail,
  serverSermonTitle,
  type SavedRecipient,
  type ServerSermonDetail,
} from '../sermons/serverSermon'

interface SelectableRecipient extends SavedRecipient {
  selected: boolean
}

const route = useRoute()
const router = useRouter()
const { isAuthenticated } = useAuth()
const sermon = ref<ServerSermonDetail>()
const loading = ref(true)
const errorMessage = ref('')
const subject = ref('')
const note = ref(
  'I wanted to share this sermon with you. The questions near the end would be good to talk through together.',
)
const recipients = ref<SelectableRecipient[]>([])
const addingRecipient = ref(false)
const recipientName = ref('')
const recipientEmail = ref('')
const savingRecipient = ref(false)
const sending = ref(false)
const sentCount = ref(0)
const shareUrl = ref('')
const composerMessage = ref('')

const selectedCount = computed(() => recipients.value.filter((recipient) => recipient.selected).length)
const shortSummary = computed(
  () =>
    sermon.value?.study_artifacts.find((artifact) => artifact.kind === 'short_summary')?.content ??
    '',
)
const capturedDate = computed(() =>
  sermon.value
    ? new Intl.DateTimeFormat(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      }).format(new Date(sermon.value.captured_at))
    : '',
)
const sermonByline = computed(() =>
  sermon.value
    ? [sermon.value.preacher?.name, sermon.value.church?.name, capturedDate.value]
        .filter(Boolean)
        .join(' · ')
    : '',
)

async function load(): Promise<void> {
  const sermonId = String(route.params.id)
  loading.value = true
  errorMessage.value = ''
  sermon.value = undefined
  sentCount.value = 0
  shareUrl.value = ''
  composerMessage.value = ''
  try {
    const [loadedSermon, savedRecipients] = await Promise.all([
      loadServerSermon(sermonId),
      loadSavedRecipients(),
    ])
    if (loadedSermon.processing_status !== 'ready') {
      errorMessage.value = loadedSermon.processing_message
      return
    }
    sermon.value = loadedSermon
    recipients.value = savedRecipients.map((recipient) => ({ ...recipient, selected: false }))
    subject.value = `${serverSermonTitle(loadedSermon)} · Shared from Pewcorder`
  } catch (error) {
    if (!isAuthenticated.value) {
      await router.replace({
        name: 'account',
        query: { redirect: `/sermons/${encodeURIComponent(sermonId)}/email` },
      })
      return
    }
    errorMessage.value =
      error instanceof Error ? error.message : 'The email composer could not be opened.'
  } finally {
    loading.value = false
  }
}

async function saveRecipient(): Promise<void> {
  if (savingRecipient.value) return
  savingRecipient.value = true
  composerMessage.value = ''
  try {
    const saved = await createSavedRecipient({
      name: recipientName.value,
      email: recipientEmail.value,
    })
    recipients.value.push({ ...saved, selected: true })
    recipients.value.sort((left, right) => left.name.localeCompare(right.name))
    recipientName.value = ''
    recipientEmail.value = ''
    addingRecipient.value = false
    composerMessage.value = 'Recipient saved for next time.'
  } catch (error) {
    composerMessage.value =
      error instanceof Error ? error.message : 'This recipient could not be saved.'
  } finally {
    savingRecipient.value = false
  }
}

async function sendEmail(): Promise<void> {
  if (!sermon.value || sending.value || selectedCount.value === 0) return
  sending.value = true
  sentCount.value = 0
  composerMessage.value = ''
  try {
    const result = await sendSermonEmail(sermon.value.id, {
      recipient_ids: recipients.value
        .filter((recipient) => recipient.selected)
        .map((recipient) => recipient.id),
      subject: subject.value,
      note: note.value,
    })
    sentCount.value = result.sent_count
    shareUrl.value = result.share_url
    composerMessage.value = `Email sent to ${result.sent_count} ${
      result.sent_count === 1 ? 'recipient' : 'recipients'
    }.`
  } catch (error) {
    composerMessage.value =
      error instanceof Error ? error.message : 'This Sermon email could not be sent.'
  } finally {
    sending.value = false
  }
}

watch(
  () => String(route.params.id),
  () => void load(),
  { immediate: true },
)
</script>

<template>
  <main class="email-composer page-gather">
    <div v-if="sentCount" class="email-sent" role="status">
      <Check :size="18" aria-hidden="true" />
      Email sent to {{ sentCount }} {{ sentCount === 1 ? 'recipient' : 'recipients' }}.
    </div>

    <button
      class="back-link"
      type="button"
      @click="router.push(`/sermons/${String(route.params.id)}`)"
    >
      <ArrowLeft :size="17" :stroke-width="1.7" aria-hidden="true" />
      Sermon
    </button>

    <p v-if="loading" class="composer-state" role="status">Opening the email desk…</p>
    <section v-else-if="errorMessage" class="composer-state composer-state--error" role="alert">
      <p class="rubric-label">Unable to compose</p>
      <h1>{{ errorMessage }}</h1>
    </section>

    <template v-else-if="sermon">
    <header class="email-composer__header">
      <p class="rubric-label">Share by email</p>
      <h1>A note worth opening.</h1>
      <p>Choose saved recipients, add a personal line, and send the Share page in a readable email.</p>
    </header>

    <div class="email-layout">
      <form class="email-form" @submit.prevent="sendEmail">
        <fieldset>
          <legend>Saved recipients</legend>
          <label v-for="recipient in recipients" :key="recipient.email" class="recipient">
            <input v-model="recipient.selected" type="checkbox" />
            <span class="recipient__check"><Check :size="14" aria-hidden="true" /></span>
            <span>
              <strong>{{ recipient.name }}</strong>
              <small>{{ recipient.email }}</small>
            </span>
          </label>
          <p v-if="!recipients.length" class="recipient-empty">
            Save an email address once, then select it whenever you share a Sermon.
          </p>
          <button
            class="add-recipient"
            type="button"
            @click="addingRecipient = !addingRecipient"
          >
            <Plus :size="16" aria-hidden="true" />
            {{ addingRecipient ? 'Cancel new recipient' : 'Add recipient' }}
          </button>
          <div v-if="addingRecipient" class="recipient-form">
            <label class="field">
              <span>Name</span>
              <input v-model="recipientName" type="text" autocomplete="name" />
            </label>
            <label class="field">
              <span>Email</span>
              <input v-model="recipientEmail" type="email" autocomplete="email" />
            </label>
            <button
              type="button"
              :disabled="savingRecipient || !recipientName.trim() || !recipientEmail.trim()"
              @click="saveRecipient"
            >
              {{ savingRecipient ? 'Saving…' : 'Save recipient' }}
            </button>
          </div>
        </fieldset>

        <label class="field">
          <span>Subject</span>
          <input v-model="subject" type="text" />
        </label>

        <label class="field">
          <span>Personal note</span>
          <textarea v-model="note" rows="5"></textarea>
        </label>

        <div class="email-form__footer">
          <span>{{ composerMessage || `${selectedCount} selected` }}</span>
          <button
            class="send-button"
            type="submit"
            :disabled="sending || selectedCount === 0 || !subject.trim()"
          >
            <Send :size="17" aria-hidden="true" />
            {{ sending ? 'Sending…' : 'Send email' }}
          </button>
        </div>
      </form>

      <aside class="email-preview" aria-label="Email preview">
        <p class="email-preview__label">Email preview</p>
        <div class="email-preview__paper">
          <BrandMark />
          <div class="email-preview__rule"></div>
          <p class="email-preview__from">Shared with you from a sermon journal</p>
          <h2>{{ serverSermonTitle(sermon) }}</h2>
          <p class="email-preview__byline">{{ sermonByline }}</p>
          <p class="email-preview__note">{{ note }}</p>
          <div class="email-preview__summary">
            <span>In brief</span>
            <p>{{ shortSummary }}</p>
          </div>
          <a :href="shareUrl || '#'" @click="!shareUrl && $event.preventDefault()">
            Read and listen
          </a>
          <p class="email-preview__privacy">
            This unlisted Share page includes the sermon audio, transcript, outline, and discussion questions.
          </p>
        </div>
      </aside>
    </div>
    </template>
  </main>
</template>

<style scoped>
.email-composer {
  margin: 0 auto;
  max-width: 70rem;
  padding: 2rem clamp(1.25rem, 4vw, 3rem) 10rem;
}

.email-sent {
  align-items: center;
  background: var(--color-lapis);
  color: var(--color-vellum-light);
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  gap: 0.55rem;
  left: 50%;
  padding: 0.8rem 1rem;
  position: fixed;
  top: calc(var(--header-height) + 1rem);
  transform: translateX(-50%);
  z-index: 60;
}

.back-link {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--color-lapis);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  gap: 0.4rem;
  padding: 0.5rem 0;
}

.composer-state {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  padding: 4rem 0;
}

.composer-state--error h1 {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 7vw, 4.5rem);
  font-weight: 520;
  letter-spacing: -0.05em;
  line-height: 0.98;
  max-width: 14ch;
}

.email-composer__header {
  border-bottom: 1px solid var(--color-rule-gold);
  margin-top: 2rem;
  padding-bottom: 2rem;
}

.email-composer__header h1 {
  font-family: var(--font-display);
  font-size: clamp(2.6rem, 6vw, 4.8rem);
  font-variation-settings: 'opsz' 72, 'SOFT' 46;
  font-weight: 520;
  letter-spacing: -0.055em;
  line-height: 0.98;
  margin: 0.55rem 0 0.9rem;
}

.email-composer__header > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.55;
  max-width: 48rem;
}

.email-layout {
  align-items: start;
  display: grid;
  gap: clamp(2rem, 6vw, 5rem);
  grid-template-columns: minmax(19rem, 0.8fr) minmax(22rem, 1.2fr);
  padding-top: 3rem;
}

.email-form {
  display: grid;
  gap: 1.5rem;
}

.email-form fieldset {
  border: 0;
  margin: 0;
  padding: 0;
}

.email-form legend,
.field > span {
  color: var(--color-rubric);
  display: block;
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.11em;
  margin-bottom: 0.65rem;
  text-transform: uppercase;
}

.recipient {
  align-items: center;
  border-top: 1px solid var(--color-margin);
  cursor: pointer;
  display: grid;
  gap: 0.75rem;
  grid-template-columns: auto 1fr;
  min-height: 3.75rem;
  position: relative;
}

.recipient input {
  opacity: 0;
  position: absolute;
}

.recipient__check {
  align-items: center;
  border: 1px solid var(--color-ink-muted);
  color: transparent;
  display: flex;
  height: 1.25rem;
  justify-content: center;
  width: 1.25rem;
}

.recipient input:checked + .recipient__check {
  background: var(--color-lapis);
  border-color: var(--color-lapis);
  color: var(--color-vellum-light);
}

.recipient input:focus-visible + .recipient__check {
  outline: 2px solid var(--color-lapis);
  outline-offset: 3px;
}

.recipient strong,
.recipient small {
  display: block;
  font-family: var(--font-utility);
}

.recipient strong {
  font-size: 0.87rem;
  font-weight: 650;
}

.recipient small {
  color: var(--color-ink-muted);
  font-size: 0.74rem;
}

.recipient-empty {
  border-top: 1px solid var(--color-margin);
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.88rem;
  line-height: 1.55;
  margin: 0;
  padding: 1rem 0;
}

.add-recipient {
  align-items: center;
  background: transparent;
  border: 0;
  border-top: 1px solid var(--color-margin);
  color: var(--color-lapis);
  cursor: pointer;
  display: flex;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  gap: 0.45rem;
  min-height: 3.25rem;
  padding: 0;
  width: 100%;
}

.recipient-form {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  display: grid;
  gap: 0.9rem;
  padding: 1rem;
}

.recipient-form button {
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-size: 0.78rem;
  font-weight: 650;
  justify-self: start;
  min-height: 2.55rem;
  padding: 0.55rem 0.8rem;
}

.recipient-form button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.field input,
.field textarea {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  color: var(--color-ink);
  font-family: var(--font-reading);
  font-size: 0.93rem;
  line-height: 1.6;
  padding: 0.85rem 1rem;
  width: 100%;
}

.field textarea {
  resize: vertical;
}

.field input:focus,
.field textarea:focus {
  border-color: var(--color-lapis);
  box-shadow: 0 0 0 3px rgba(47, 75, 124, 0.11);
  outline: 0;
}

.email-form__footer {
  align-items: center;
  border-top: 1px solid var(--color-margin);
  display: flex;
  justify-content: space-between;
  padding-top: 1rem;
}

.email-form__footer > span {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.76rem;
}

.send-button {
  align-items: center;
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-size: 0.82rem;
  font-weight: 650;
  gap: 0.5rem;
  min-height: 2.85rem;
  padding: 0.7rem 1.05rem;
}

.send-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.email-preview {
  position: sticky;
  top: calc(var(--header-height) + 2rem);
}

.email-preview__label {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
  font-size: 0.68rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  margin: 0 0 0.65rem;
  text-transform: uppercase;
}

.email-preview__paper {
  background: #fffdf7;
  border: 1px solid var(--color-margin);
  box-shadow: 0 16px 45px var(--color-paper-shadow);
  padding: clamp(1.5rem, 5vw, 3.5rem);
}

.email-preview__rule {
  background: var(--color-rule-gold);
  height: 1px;
  margin: 1.8rem 0;
}

.email-preview__from,
.email-preview__byline,
.email-preview__privacy {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
}

.email-preview__from {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.email-preview h2 {
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 5vw, 3.6rem);
  font-weight: 520;
  letter-spacing: -0.05em;
  line-height: 0.98;
  margin: 0.6rem 0 0.8rem;
}

.email-preview__byline {
  font-size: 0.75rem;
}

.email-preview__note {
  font-family: var(--font-reading);
  font-size: 0.95rem;
  line-height: 1.65;
  margin: 1.8rem 0;
}

.email-preview__summary {
  border-left: 2px solid var(--color-rubric);
  padding-left: 1rem;
}

.email-preview__summary span {
  color: var(--color-rubric);
  font-family: var(--font-utility);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.email-preview__summary p {
  font-family: var(--font-reading);
  font-size: 0.94rem;
  line-height: 1.6;
  margin: 0.5rem 0 0;
}

.email-preview__paper > a {
  background: var(--color-lapis);
  color: #fffdf7;
  display: inline-block;
  font-family: var(--font-utility);
  font-size: 0.8rem;
  font-weight: 650;
  margin-top: 1.8rem;
  padding: 0.75rem 1rem;
  text-decoration: none;
}

.email-preview__privacy {
  font-size: 0.68rem;
  line-height: 1.45;
  margin: 1.25rem 0 0;
}

@media (max-width: 820px) {
  .email-layout {
    grid-template-columns: 1fr;
  }

  .email-preview {
    position: static;
  }
}
</style>
