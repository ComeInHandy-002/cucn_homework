import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/overview' },
  { path: '/overview', name: 'overview', component: () => import('./views/OverviewView.vue'), meta: { title: '监控总览', eyebrow: 'OPERATION CENTER' } },
  { path: '/detection', name: 'detection', component: () => import('./views/DetectionView.vue'), meta: { title: '智能检测', eyebrow: 'AI INFERENCE' } },
  { path: '/jobs', name: 'jobs', component: () => import('./views/JobsView.vue'), meta: { title: '任务中心', eyebrow: 'INFERENCE JOBS' } },
  { path: '/experiments', name: 'experiments', component: () => import('./views/ExperimentsView.vue'), meta: { title: '模型实验', eyebrow: 'MODEL & DATA LAB' } },
  { path: '/alerts', name: 'alerts', component: () => import('./views/AlertsView.vue'), meta: { title: '告警中心', eyebrow: 'SAFETY EVENTS' } },
  { path: '/configuration', name: 'configuration', component: () => import('./views/ConfigurationView.vue'), meta: { title: '设备与区域', eyebrow: 'SYSTEM CONFIGURATION' } }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
