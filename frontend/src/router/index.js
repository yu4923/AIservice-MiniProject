import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', alias: '/intro_main.html', component: () => import('../views/HomeView.vue'), meta: { title: 'RAG Pipeline API App' } },
    { path: '/external', alias: '/external_index.html', component: () => import('../views/ExternalRagView.vue'), meta: { title: 'Closed Source LLM Console' } },
    { path: '/internal', alias: '/internal_index.html', component: () => import('../views/InternalRagView.vue'), meta: { title: 'Open Weight LLM Console' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => { document.title = to.meta.title || "RAG Pipeline API App" })

export default router
