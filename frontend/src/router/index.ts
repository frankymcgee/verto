import { createRouter, createWebHistory } from 'vue-router'

import MobileShell from '../layouts/MobileShell.vue'
import Home from '../pages/Home.vue'
import Forms from '../pages/Forms.vue'
import Shifts from '../pages/Shifts.vue'
import Chat from '../pages/Chat.vue'
import NewDocument from '../pages/NewDocument.vue'
import EditDocument from '../pages/EditDocument.vue'

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