<script setup lang="ts">
import { BookOpenText, Library, Search } from '@lucide/vue'
</script>

<template>
  <nav class="app-navigation" aria-label="Primary navigation">
    <div class="app-navigation__inner">
      <RouterLink class="app-navigation__item" to="/">
        <Library :size="20" :stroke-width="1.7" aria-hidden="true" />
        <span>Library</span>
      </RouterLink>
      <RouterLink class="app-navigation__item" :to="{ path: '/', query: { focus: 'search' } }">
        <Search :size="20" :stroke-width="1.7" aria-hidden="true" />
        <span>Search</span>
      </RouterLink>
      <RouterLink class="app-navigation__item" to="/sermons/come-and-rest#reflection">
        <BookOpenText :size="20" :stroke-width="1.7" aria-hidden="true" />
        <span>Reflect</span>
      </RouterLink>
      <span class="app-navigation__record-space" aria-hidden="true"></span>
    </div>
  </nav>
</template>

<style scoped>
.app-navigation {
  background: color-mix(in srgb, var(--color-vellum) 94%, transparent);
  border-top: 1px solid var(--color-margin);
  bottom: 0;
  left: 0;
  min-height: calc(var(--nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  position: fixed;
  right: 0;
  z-index: 30;
}

.app-navigation__inner {
  align-items: center;
  display: grid;
  grid-template-columns: repeat(3, minmax(4.25rem, 6rem)) 6.6rem;
  height: var(--nav-height);
  margin: 0 auto;
  max-width: var(--page-width);
  padding-inline: 1rem;
}

.app-navigation__item {
  align-items: center;
  color: var(--color-ink-muted);
  display: flex;
  flex-direction: column;
  font-family: var(--font-utility);
  font-size: 0.72rem;
  font-weight: 600;
  gap: 0.28rem;
  justify-content: center;
  min-height: 3.75rem;
  text-decoration: none;
  transition: color 160ms ease;
}

.app-navigation__item:hover,
.app-navigation__item:focus-visible,
.app-navigation__item.router-link-exact-active {
  color: var(--color-lapis);
}

.app-navigation__item:focus-visible {
  outline: 2px solid var(--color-lapis);
  outline-offset: -3px;
}

@media (min-width: 760px) {
  .app-navigation__inner {
    grid-template-columns: repeat(3, 6.5rem) 1fr 7rem;
  }

  .app-navigation__record-space {
    grid-column: 5;
  }
}

@media (max-width: 420px) {
  .app-navigation__inner {
    grid-template-columns: repeat(3, minmax(3.75rem, 1fr)) 5.5rem;
    padding-inline: 0.4rem;
  }
}
</style>
