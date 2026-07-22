<script setup lang="ts">
import { computed, ref } from 'vue'
import { BellRing, LogOut, ShieldCheck } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import {
  availableSocialProviders,
  type SocialProvider,
} from '../auth/socialLogin'
import { useAuth } from '../auth/useAuth'
import { useProcessingAlerts } from '../notifications/useProcessingAlerts'

const route = useRoute()
const router = useRouter()
const mode = ref<'sign-in' | 'register'>('sign-in')
const email = ref('')
const password = ref('')
const displayName = ref('')
const alertBusy = ref(false)
const {
  user,
  busy,
  errorMessage,
  isAuthenticated,
  login,
  loginWithSocial,
  register,
  logout,
} = useAuth()
const {
  available: alertsAvailable,
  state: alertState,
  errorMessage: alertError,
  enabled: alertsEnabled,
  enable: enableAlerts,
  disconnect: disconnectAlerts,
} = useProcessingAlerts()

const heading = computed(() => (mode.value === 'sign-in' ? 'Return to your library.' : 'Begin your library.'))
const redirectPath = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/'
})

async function submit(): Promise<void> {
  try {
    if (mode.value === 'register') {
      await register(email.value, password.value, displayName.value)
    } else {
      await login(email.value, password.value)
    }
    await router.replace(redirectPath.value)
  } catch {
    // The shared auth state presents the server's actionable error.
  }
}

async function continueWith(provider: SocialProvider): Promise<void> {
  try {
    await loginWithSocial(provider)
    await router.replace(redirectPath.value)
  } catch {
    // The shared auth state presents provider and server errors.
  }
}

async function requestAlerts(): Promise<void> {
  alertBusy.value = true
  try {
    await enableAlerts()
  } finally {
    alertBusy.value = false
  }
}

async function signOut(): Promise<void> {
  alertBusy.value = true
  try {
    await disconnectAlerts()
  } finally {
    logout()
    alertBusy.value = false
  }
}
</script>

<template>
  <main class="account page-gather">
    <section class="account__heading">
      <p class="rubric-label">Your Pewcorder account</p>
      <h1>{{ isAuthenticated ? 'Your library is connected.' : heading }}</h1>
      <p>
        Drafts stay on this device until you choose to upload them. Signing in connects uploaded
        Sermons to your private library.
      </p>
    </section>

    <section v-if="isAuthenticated && user" class="account-card">
      <span class="account-card__seal" aria-hidden="true">
        <ShieldCheck :size="30" :stroke-width="1.5" />
      </span>
      <p class="rubric-label">Signed in</p>
      <h2>{{ user.display_name || 'Pewcorder Congregant' }}</h2>
      <p>{{ user.email }}</p>
      <div v-if="alertsAvailable" class="completion-alerts">
        <BellRing :size="21" :stroke-width="1.6" aria-hidden="true" />
        <div>
          <strong>Completion alerts</strong>
          <p v-if="alertsEnabled">This device will tell you when processing finishes.</p>
          <p v-else-if="alertState === 'denied'">
            Notifications are off in this device’s system settings.
          </p>
          <p v-else>Let Pewcorder tell you when a Sermon is ready or needs attention.</p>
          <p v-if="alertError" class="completion-alerts__error" role="alert">
            {{ alertError }}
          </p>
        </div>
        <button
          v-if="!alertsEnabled && alertState !== 'denied'"
          type="button"
          :disabled="alertBusy || alertState === 'registering'"
          @click="requestAlerts"
        >
          {{ alertBusy || alertState === 'registering' ? 'Connecting…' : 'Enable' }}
        </button>
      </div>
      <button type="button" :disabled="alertBusy" @click="signOut">
        <LogOut :size="17" aria-hidden="true" />
        Sign out
      </button>
    </section>

    <section v-else class="account-form">
      <div class="account-form__tabs" role="group" aria-label="Account action">
        <button
          type="button"
          :class="{ active: mode === 'sign-in' }"
          :aria-pressed="mode === 'sign-in'"
          @click="mode = 'sign-in'"
        >
          Sign in
        </button>
        <button
          type="button"
          :class="{ active: mode === 'register' }"
          :aria-pressed="mode === 'register'"
          @click="mode = 'register'"
        >
          Create account
        </button>
      </div>

      <div v-if="availableSocialProviders.length" class="social-login">
        <button
          v-for="provider in availableSocialProviders"
          :key="provider"
          type="button"
          :disabled="busy"
          @click="continueWith(provider)"
        >
          Continue with {{ provider === 'apple' ? 'Apple' : 'Google' }}
        </button>
      </div>
      <p v-if="errorMessage" class="account-form__error" role="alert">{{ errorMessage }}</p>
      <div v-if="availableSocialProviders.length" class="account-form__divider">
        <span>or use email</span>
      </div>

      <form @submit.prevent="submit">
        <label v-if="mode === 'register'">
          <span>Your name</span>
          <input v-model="displayName" autocomplete="name" placeholder="How Pewcorder should greet you" />
        </label>
        <label>
          <span>Email</span>
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label>
          <span>Password</span>
          <input
            v-model="password"
            type="password"
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
            minlength="8"
            required
          />
        </label>
        <button class="account-form__submit" type="submit" :disabled="busy">
          {{ busy ? 'Please wait…' : mode === 'sign-in' ? 'Sign in' : 'Create private library' }}
        </button>
      </form>

      <p class="account-form__privacy">
        Recording never requires an account. Authentication is requested only when a Draft leaves
        this device.
      </p>
    </section>
  </main>
</template>

<style scoped>
.account {
  margin: 0 auto;
  max-width: 64rem;
  min-height: calc(100svh - var(--header-height));
  padding: 0 clamp(1.25rem, 4vw, 3rem) 8rem;
}

.account__heading {
  border-bottom: 1px solid var(--color-rule-gold);
  padding: clamp(3.5rem, 8vw, 6.5rem) 0 2rem;
}

.account__heading h1 {
  font-size: clamp(2.1rem, 7vw, 4rem);
  line-height: 0.98;
  margin: 0.6rem 0 1rem;
  max-width: 12ch;
}

.account__heading > p:last-child {
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  line-height: 1.65;
  max-width: 39rem;
}

.account-card,
.account-form {
  background: var(--color-vellum-light);
  border: 1px solid var(--color-margin);
  box-shadow: 0 18px 50px var(--color-paper-shadow);
  margin: 2.5rem auto 0;
  max-width: 32rem;
  padding: clamp(1.5rem, 5vw, 2.5rem);
}

.account-card {
  text-align: center;
}

.account-card__seal {
  align-items: center;
  border: 1px solid var(--color-rule-gold);
  border-radius: 50%;
  color: var(--color-lapis);
  display: inline-flex;
  height: 4.2rem;
  justify-content: center;
  margin-bottom: 1.2rem;
  width: 4.2rem;
}

.account-card h2 {
  font-family: var(--font-display);
  font-size: 1.8rem;
  margin: 0.5rem 0 0.2rem;
}

.account-card > p:not(.rubric-label) {
  color: var(--color-ink-muted);
  font-family: var(--font-utility);
}

.completion-alerts {
  align-items: start;
  background: var(--color-vellum);
  border-left: 2px solid var(--color-lapis);
  display: grid;
  gap: 0.75rem;
  grid-template-columns: auto 1fr auto;
  margin-top: 1.5rem;
  padding: 1rem;
  text-align: left;
}

.completion-alerts > svg {
  color: var(--color-lapis);
  margin-top: 0.1rem;
}

.completion-alerts strong,
.completion-alerts p {
  font-family: var(--font-utility);
}

.completion-alerts strong {
  font-size: 0.82rem;
}

.completion-alerts p {
  color: var(--color-ink-muted);
  font-size: 0.74rem;
  line-height: 1.45;
  margin: 0.2rem 0 0;
}

.completion-alerts .completion-alerts__error {
  color: var(--color-rubric);
}

.account-card .completion-alerts button {
  margin: 0;
  min-height: 2.3rem;
  padding: 0.4rem 0.7rem;
}

.account-card button,
.account-form__submit {
  align-items: center;
  background: var(--color-lapis);
  border: 0;
  color: var(--color-vellum-light);
  cursor: pointer;
  display: inline-flex;
  font-family: var(--font-utility);
  font-weight: 700;
  gap: 0.45rem;
  justify-content: center;
  margin-top: 1.5rem;
  min-height: 3rem;
  padding: 0.75rem 1.15rem;
}

.account-card button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.account-form__tabs {
  border-bottom: 1px solid var(--color-margin);
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: -0.5rem 0 1.5rem;
}

.account-form__tabs button {
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--color-ink-muted);
  cursor: pointer;
  font-family: var(--font-utility);
  font-weight: 700;
  padding: 0.9rem 0.5rem;
}

.account-form__tabs button.active {
  border-bottom-color: var(--color-rubric);
  color: var(--color-ink);
}

.social-login {
  display: grid;
  gap: 0.7rem;
}

.social-login button {
  background: var(--color-ink);
  border: 1px solid var(--color-ink);
  color: var(--color-vellum-light);
  cursor: pointer;
  font-family: var(--font-utility);
  font-weight: 700;
  min-height: 3rem;
}

.social-login button:last-child {
  background: var(--color-vellum);
  border-color: var(--color-margin);
  color: var(--color-ink);
}

.social-login button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.account-form__divider {
  align-items: center;
  color: var(--color-ink-muted);
  display: grid;
  font-family: var(--font-utility);
  font-size: 0.7rem;
  gap: 0.75rem;
  grid-template-columns: 1fr auto 1fr;
  margin: 1.25rem 0;
  text-transform: uppercase;
}

.account-form__divider::before,
.account-form__divider::after {
  background: var(--color-margin);
  content: '';
  height: 1px;
}

.account-form label,
.account-form label span {
  display: block;
}

.account-form label + label {
  margin-top: 1rem;
}

.account-form label span {
  color: var(--color-ink);
  font-family: var(--font-utility);
  font-size: 0.76rem;
  font-weight: 700;
  margin-bottom: 0.35rem;
}

.account-form input {
  background: var(--color-vellum);
  border: 1px solid var(--color-margin);
  border-radius: 0;
  color: var(--color-ink);
  font: 1rem var(--font-utility);
  min-height: 3rem;
  padding: 0.7rem 0.8rem;
  width: 100%;
}

.account-form input:focus {
  border-color: var(--color-lapis);
  outline: 2px solid color-mix(in srgb, var(--color-lapis) 25%, transparent);
}

.account-form__submit {
  width: 100%;
}

.account-form__submit:disabled {
  cursor: wait;
  opacity: 0.7;
}

.account-form__error {
  color: var(--color-rubric);
  font-family: var(--font-utility);
  font-size: 0.82rem;
  margin: 1rem 0 0;
}

.account-form__privacy {
  border-top: 1px solid var(--color-margin);
  color: var(--color-ink-muted);
  font-family: var(--font-reading);
  font-size: 0.8rem;
  line-height: 1.5;
  margin: 1.5rem 0 0;
  padding-top: 1rem;
}
</style>
