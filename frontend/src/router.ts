import { createRouter, createWebHistory } from 'vue-router'
import EmailComposerView from './views/EmailComposerView.vue'
import LibraryView from './views/LibraryView.vue'
import SermonView from './views/SermonView.vue'
import ShareView from './views/ShareView.vue'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to) {
    if (to.hash) {
      return {
        el: to.hash,
        behavior: 'smooth',
      }
    }

    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'library',
      component: LibraryView,
    },
    {
      path: '/sermons/:id',
      name: 'sermon',
      component: SermonView,
    },
    {
      path: '/sermons/:id/email',
      name: 'email',
      component: EmailComposerView,
    },
    {
      path: '/share/:token',
      name: 'share',
      component: ShareView,
      meta: { public: true },
    },
  ],
})

export default router
