<template>
  <Popover side="bottom" align="start" bare>
    <template #trigger>
      <button
        type="button"
        aria-label="Apps menu"
        class="planner-apps-trigger flex items-center gap-1.5 rounded-6 border px-3 py-1.5 text-xs-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900"
      >
        <Icon name="lucide-grid" class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">{{ translate("Apps") }}</span>
        <Icon name="lucide-chevron-down" class="h-3.5 w-3.5 text-gray-400" />
      </button>
    </template>

    <template #default>
      <div
        class="planner-apps-popover rounded-7 border border-gray-100 bg-white p-2 shadow-xl"
      >
        <div class="grid grid-cols-3 gap-1.5">
          <a
            v-for="app in appOptions"
            :key="app.name"
            :href="app.route"
            class="planner-app-tile flex flex-col items-center justify-center gap-1.5 rounded-6 px-3 py-2 text-center transition hover:bg-gray-50"
            @click="app.onClick"
          >
            <img
              v-if="app.logo"
              class="h-8 w-8 rounded-6 object-contain"
              :src="app.logo"
              :alt="app.title"
            />
            <div
              v-else
              class="planner-app-fallback flex h-8 w-8 items-center justify-center rounded-6 text-xs-bold text-white"
            >
              {{ app.title?.charAt(0) || "A" }}
            </div>

            <div class="max-w-[72px] truncate text-xs-medium text-gray-700">
              {{ app.title }}
            </div>
          </a>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { usePlannerSettings } from "../utils/settings";
import { Icon, Popover } from "frappe-ui";
import { usePlannerBootstrap } from "../utils/bootstrap";

type AppOption = {
  name: string;
  logo?: string;
  title: string;
  route: string;
  onClick?: () => void;
};

type VertoMobileSettings = {
  planner_app_name?: string;
  desk_icon?: string;
  planner_icon?: string;
};

function translate(value: string) {
  const globalTranslate = (window as any).__;
  return typeof globalTranslate === "function" ? globalTranslate(value) : value;
}

const settings = usePlannerSettings();

const bootstrap = usePlannerBootstrap();

const vertoSettings = computed<VertoMobileSettings>(() => {
  return (settings.data || {}) as VertoMobileSettings;
});

const plannerAppName = computed(() => {
  return vertoSettings.value.planner_app_name?.trim() || translate("Planner");
});

const deskIcon = computed(() => {
  return vertoSettings.value.desk_icon || "";
});

const plannerIcon = computed(() => {
  return vertoSettings.value.planner_icon || "";
});

const appOptions = computed<AppOption[]>(() => {
  const mappedApps: AppOption[] = [
    {
      name: "frappe",
      logo: deskIcon.value,
      title: translate("Desk"),
      route: "/app",
    },
    {
      name: "planner",
      logo: plannerIcon.value,
      title: plannerAppName.value,
      route: "/planner",
    },
  ];

  for (const app of (bootstrap.data?.apps || []) as AppOption[]) {
    if (!app?.name) continue;

    // Desk and Planner are controlled by Verto Mobile Settings above.
    if (["frappe", "verto", "planner"].includes(app.name)) continue;

    mappedApps.push({
      name: app.name,
      logo: app.logo,
      title: translate(app.title || app.name),
      route: app.route || "/app",
    });
  }

  return mappedApps;
});
</script>

<style scoped>
.planner-apps-popover {
  width: 300px;
}

.planner-app-tile {
  text-decoration: none;
}

.planner-app-fallback {
  background:
    radial-gradient(circle at 30% 20%, rgb(96 165 250), transparent 34%),
    linear-gradient(135deg, rgb(37 99 235), rgb(14 165 233) 52%, rgb(15 23 42));
}
</style>
