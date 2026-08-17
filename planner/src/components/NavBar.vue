<template>
	<header class="planner-navbar sticky top-0 z-40 h-14 border-b bg-white/95 px-4 shadow-sm backdrop-blur md:px-8">
		<div class="flex h-full items-center gap-3">
			<a href="/planner" class="planner-brand group flex min-w-0 items-center gap-3">
				<div class="planner-logo flex h-9 w-9 shrink-0 items-center justify-center rounded-xl">
					<img
						v-if="plannerIcon"
						class="h-8 w-8 rounded-lg object-contain"
						:src="plannerIcon"
						:alt="plannerAppName"
					/>

					<span v-else class="text-sm font-black leading-none text-white">
						{{ plannerAppInitial }}
					</span>
				</div>

				<div class="min-w-0 leading-tight">
					<div class="truncate text-sm font-semibold text-gray-900 group-hover:text-gray-700">
						{{ plannerAppName }}
					</div>
					<div class="hidden truncate text-xs text-gray-500 sm:block">
						Workforce, project and roster planning
					</div>
				</div>
			</a>

			<div class="ml-auto flex items-center gap-2">
				<Apps />

				<Dropdown
					:options="[
						{
							label: 'Reload Planner',
							onClick: reloadPlanner,
						},
						{
							label: 'My Profile',
							onClick: () => goTo('/me'),
						},
						{
							label: 'Log Out',
							onClick: () => logout.submit(),
						},
					]"
				>
					<div class="planner-avatar-trigger flex cursor-pointer items-center gap-2 rounded-full p-1 transition hover:bg-gray-100">
						<Avatar
							:label="props.user?.full_name"
							:image="props.user?.user_image"
							size="lg"
						/>

						<div class="hidden max-w-[160px] leading-tight md:block">
							<div class="truncate text-xs font-semibold text-gray-800">
								{{ props.user?.full_name || 'User' }}
							</div>
							<div class="truncate text-[11px] text-gray-500">
								Account
							</div>
						</div>

						<FeatherIcon name="chevron-down" class="hidden h-4 w-4 text-gray-400 md:block" />
					</div>
				</Dropdown>
			</div>
		</div>
	</header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { FeatherIcon, Dropdown, Avatar, createResource } from "frappe-ui";

import Apps from "./Apps.vue";
import { User } from "../views/Home.vue";
import { goTo, raiseToast } from "../utils/index.js";

type VertoMobileSettings = {
	planner_app_name?: string;
	planner_icon?: string;
};

const props = defineProps<{
	user: User;
}>();

function translate(value: string) {
	const globalTranslate = (window as any).__;
	return typeof globalTranslate === "function" ? globalTranslate(value) : value;
}

function reloadPlanner() {
	window.location.reload();
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
	onError(error: { messages?: string[]; message?: string }) {
		raiseToast("error", error.messages?.[0] || error.message || "Unable to load Verto Mobile Settings");
	},
});

const vertoSettings = computed<VertoMobileSettings>(() => {
	return (settings.data || {}) as VertoMobileSettings;
});

const plannerAppName = computed(() => {
	return vertoSettings.value.planner_app_name?.trim() || translate("Planner");
});

const plannerIcon = computed(() => {
	return vertoSettings.value.planner_icon || "";
});

const plannerAppInitial = computed(() => {
	return plannerAppName.value?.trim()?.charAt(0)?.toUpperCase() || "P";
});

// RESOURCES

const logout = createResource({
	url: "logout",
	onSuccess() {
		goTo("/login");
	},
	onError(error: { messages?: string[]; message?: string }) {
		raiseToast("error", error.messages?.[0] || error.message || "Unable to log out");
	},
});
</script>

<style scoped>
.planner-navbar {
	min-height: 56px;
}

.planner-logo {
	box-shadow:
		0 8px 18px rgba(44, 44, 44, 0.22),
		inset 0 0 0 1px rgb(255 255 255 / 0.28);
}

.planner-brand {
	text-decoration: none;
}

.planner-avatar-trigger {
	outline: none;
}
</style>
