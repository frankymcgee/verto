<template>
	<Popover placement="bottom-start">
		<template #target="{ togglePopover }">
			<button
				type="button"
				class="planner-apps-trigger flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900"
				@click.prevent="togglePopover()"
			>
				<FeatherIcon name="grid" class="h-3.5 w-3.5" />
				<span class="hidden sm:inline">{{ translate("Apps") }}</span>
				<FeatherIcon name="chevron-down" class="h-3.5 w-3.5 text-gray-400" />
			</button>
		</template>

		<template #body>
			<div class="planner-apps-popover rounded-xl border border-gray-100 bg-white p-2 shadow-xl">
				<div class="grid grid-cols-3 gap-1.5">
					<a
						v-for="app in appOptions"
						:key="app.name"
						:href="app.route"
						class="planner-app-tile flex flex-col items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-center transition hover:bg-gray-50"
						@click="app.onClick"
					>
						<img
							v-if="app.logo"
							class="h-8 w-8 rounded-lg object-contain"
							:src="app.logo"
							:alt="app.title"
						/>
						<div
							v-else
							class="planner-app-fallback flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
						>
							{{ app.title?.charAt(0) || "A" }}
						</div>

						<div class="max-w-[72px] truncate text-xs font-medium text-gray-700">
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
import { FeatherIcon, Popover, createResource } from "frappe-ui";

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

const settings = createResource({
	url: "frappe.client.get",
	cache: "verto-mobile-settings",
	auto: true,
	makeParams() {
		return {
			doctype: "Verto Mobile Settings",
			name: "Verto Mobile Settings",
		};
	},
});

const apps = createResource({
	url: "frappe.apps.get_apps",
	cache: "planner-apps",
	auto: true,
	transform(data: AppOption[]) {
		return data || [];
	},
});

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

	for (const app of ((apps.data || []) as AppOption[])) {
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
