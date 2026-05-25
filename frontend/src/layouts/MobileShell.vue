<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <main class="mx-auto min-h-screen max-w-md pb-20">
      <router-view />
    </main>

    <BottomTabs />
  </div>
</template>

<script setup lang="ts">
import BottomTabs from '../components/BottomTabs.vue'
</script>