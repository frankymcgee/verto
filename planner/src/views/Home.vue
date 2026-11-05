<template>
  <div v-if="bootstrap.data?.user" class="min-h-screen">
    <div v-if="Object.keys(bootstrap.data.errors || {}).length" role="alert" class="bg-amber-50 px-6 py-2 text-sm">
      Some planner options could not be loaded. Check your permissions or
      <button class="underline" @click="bootstrap.fetch({})">retry</button>.
    </div>
    <NavBar :user="bootstrap.data.user" />
    <MonthView />
  </div>
  <div v-else-if="bootstrap.error" role="alert" class="p-8">
    Unable to load the planner.
    <button class="underline" @click="bootstrap.fetch({})">Retry</button>
  </div>
  <div v-else class="p-8 text-gray-500">Loading planner...</div>
</template>

<script setup lang="ts">
import { watch } from "vue";
import { usePlannerBootstrap } from "../utils/bootstrap";

import NavBar from "../components/NavBar.vue";
import MonthView from "./MonthView.vue";

export type User = {
  [K in "name" | "first_name" | "full_name" | "user_image"]: string;
} & {
  roles: string[];
};

const bootstrap = usePlannerBootstrap();
watch(() => bootstrap.error, (error: any) => {
  if (error?.status === 401 || error?.exc_type === "AuthenticationError") {
    window.location.href = "/login?redirect-to=%2Fplanner";
  }
});
</script>
