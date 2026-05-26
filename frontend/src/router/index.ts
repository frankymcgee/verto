import { createRouter, createWebHistory } from 'vue-router'

import MobileShell from '../layouts/MobileShell.vue'
import Home from '../pages/Home.vue'
import Forms from '../pages/Forms.vue'
import Shifts from '../pages/Shifts.vue'
import Chat from '../pages/Chat.vue'
import More from '../pages/More.vue'
import NewDocument from '../pages/NewDocument.vue'

const routes = [
  {
    path: '/',
    component: MobileShell,
    children: [
      {
        path: '',
        component: Home,
        meta: {
          title: 'My Site Work',
        },
      },
      {
        path: 'forms',
        component: Forms,
        meta: {
          title: 'Completed Forms',
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
        path: 'more',
        component: More,
        meta: {
          title: 'More',
        },
      },
      {
        path: 'new/:mobileDoctype',
        component: NewDocument,
        meta: {
          title: 'New Form',
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