import { createRouter, createWebHistory } from 'vue-router'

import MobileShell from '../layouts/MobileShell.vue'
import Home from '../pages/Home.vue'
import Forms from '../pages/Forms.vue'
import Shifts from '../pages/Shifts.vue'
import Chat from '../pages/Chat.vue'
import More from '../pages/More.vue'
import NewDocument from '../pages/NewDocument.vue'
import EditDocument from '../pages/EditDocument.vue'

const routes = [
  {
    path: '/',
    component: MobileShell,
    children: [
      { path: '', component: Home },
      { path: 'forms', component: Forms },
      { path: 'shifts', component: Shifts },
      { path: 'chat', component: Chat },
      { path: 'more', component: More },

      // Create a new mobile document
      {
        path: 'new/:mobileDoctype',
        component: NewDocument,
      },

      // Edit an existing mobile document
      {
        path: 'edit/:mobileDoctype/:docname',
        component: EditDocument,
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