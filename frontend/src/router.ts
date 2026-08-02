import { createRouter, createWebHistory } from 'vue-router'

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
      component: () => import('./views/LibraryView.vue'),
      meta: { keepAlive: true },
    },
    {
      path: '/sermons/:id',
      name: 'sermon',
      component: () => import('./views/SermonView.vue'),
    },
    {
      path: '/sermons/:id/email',
      name: 'email',
      component: () => import('./views/EmailComposerView.vue'),
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('./views/AccountView.vue'),
    },
    {
      path: '/share/:token',
      name: 'share',
      component: () => import('./views/ShareView.vue'),
      meta: { public: true },
    },
  ],
})

export default router
