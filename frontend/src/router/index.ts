import { createRouter, createWebHistory } from 'vue-router'

import MobileShell from '../layouts/MobileShell.vue'

const Home = () => import('../pages/Home.vue')
const Forms = () => import('../pages/Forms.vue')
const Shifts = () => import('../pages/Shifts.vue')
const Chat = () => import('../pages/Chat.vue')
const NewDocument = () => import('../pages/NewDocument.vue')
const EditDocument = () => import('../pages/EditDocument.vue')
const VoiceJha = () => import('../pages/VoiceJha.vue')

const routes = [
  {
    path: '/',
    component: MobileShell,
    children: [
      {
        path: '',
        component: Home,
        meta: {
          title: 'Home',
        },
      },
      {
        path: 'forms',
        component: Forms,
        meta: {
          title: 'Forms',
        },
      },
      {
        path: 'shifts',
        component: Shifts,
        meta: {
          title: 'Shifts',
        },
      },
      {
        path: 'chat',
        component: Chat,
        meta: {
          title: 'Chat',
        },
      },
      {
        path: 'chat/peri',
        component: Chat,
        meta: {
          title: 'Ask PERI',
          mode: 'peri',
        },
      },
      {
        path: 'voice-jha/:workSummary',
        component: VoiceJha,
        meta: {
          title: 'Develop JHA with PERI',
        },
      },
      {
        path: 'new/:mobileDoctype',
        component: NewDocument,
        meta: {
          title: 'New Form',
        },
      },
      {
        path: 'edit/:mobileDoctype/:docname',
        component: EditDocument,
        meta: {
          title: 'Edit Form',
        },
      },
    ],
  },
]

export default createRouter({
  history: createWebHistory('/verto-mobile/'),
  routes,
  scrollBehavior() {
    return { top: 0, left: 0 }
  },
})