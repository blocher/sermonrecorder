<script setup lang="ts">
import { computed, ref } from 'vue'
import { LogOut, ShieldCheck } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../auth/useAuth'

const route = useRoute()
const router = useRouter()
const mode = ref<'sign-in' | 'register'>('sign-in')
const email = ref('')
const password = ref('')
const displayName = ref('')
const { user, busy, errorMessage, isAuthenticated, login, register, logout } = useAuth()

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
      <h2>{{ user.display_name || 'Pewcorder listener' }}</h2>
      <p>{{ user.email }}</p>
      <button type="button" @click="logout">
        <LogOut :size="17" aria-hidden="true" />
        Sign out
      </button>
    </section>

    <section v-else class="account-form">
      <div class="account-form__tabs" aria-label="Account action">
        <button
          type="button"
          :class="{ active: mode === 'sign-in' }"
          @click="mode = 'sign-in'"
        >
          Sign in
        </button>
        <button
          type="button"
          :class="{ active: mode === 'register' }"
          @click="mode = 'register'"
        >
          Create account
        </button>
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

        <p v-if="errorMessage" class="account-form__error" role="alert">{{ errorMessage }}</p>

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
  min-height: calc(100svh - var(--header-height) - var(--nav-height));
  padding-bottom: calc(var(--nav-height) + 5rem);
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
