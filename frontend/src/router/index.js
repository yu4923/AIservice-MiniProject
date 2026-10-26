import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../views/WelcomeView.vue'), meta: { title: 'Youth Compass · 시작하기' } },
    { path: '/home', component: () => import('../views/YouthCompassView.vue'), meta: { title: 'Youth Compass · 청년정책 나침반' } },
    { path: '/:page(categories|login|signup|search|chat)', component: () => import('../views/YouthCompassView.vue'), meta: { title: 'Youth Compass · 청년정책 나침반' } },
    { path: '/recommendations', redirect: '/search' },
    { path: '/survey/:step', component: () => import('../views/YouthCompassView.vue'), meta: { title: 'Youth Compass · 맞춤 설문' } },
    { path: '/console', alias: '/intro_main.html', component: () => import('../views/HomeView.vue'), meta: { title: 'RAG Pipeline API App' } },
    { path: '/external', alias: '/external_index.html', component: () => import('../views/ExternalRagView.vue'), meta: { title: 'Closed Source LLM Console' } },
    { path: '/internal', alias: '/internal_index.html', component: () => import('../views/InternalRagView.vue'), meta: { title: 'Open Weight LLM Console' } },
  ],
  async scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) {
      await nextTick()
      await Promise.all([...document.images].map(image => image.decode().catch(() => {})))
      return { el: to.hash, top: (document.querySelector('.site-nav')?.getBoundingClientRect().height || 64) + 16, behavior: (to.path === from.path || ['#policy-categories', '#how'].includes(to.hash)) && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'instant' }
    }
    return { top: 0, behavior: 'instant' }
  },
})

router.afterEach((to) => { document.title = to.meta.title || "RAG Pipeline API App" })

export default router
