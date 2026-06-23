<template>
	<Teleport to="body">
		<div
			v-if="dialogOpen"
			class="fixed inset-0 z-[9998] bg-black/50"
			@click.self="closeDialog"
		/>

		<div
			v-if="dialogOpen"
			class="fixed inset-0 z-[9999] flex items-start justify-center overflow-y-auto px-4 py-10"
			@click.self="closeDialog"
		>
			<div
				class="w-full max-w-5xl overflow-hidden rounded-lg bg-white shadow-2xl"
				role="dialog"
				aria-modal="true"
				:aria-label="dialog.title"
				@click.stop
			>
				<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
					<h2 class="text-xl font-semibold text-gray-900">{{ dialog.title }}</h2>
					<button
						type="button"
						class="rounded-md p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
						aria-label="Close"
						@click="closeDialog"
					>
						✕
					</button>
				</div>

				<div class="max-h-[calc(100vh-13rem)] overflow-y-auto px-6 py-5">
					<div class="grid grid-cols-2 gap-6">
						<FormControl
							type="autocomplete"
							label="Employee"
							v-model="form.employee"
							:disabled="!!props.shiftAssignmentName"
							:options="employees"
						/>
						<FormControl type="text" label="Company" v-model="form.company" :disabled="true" />

						<FormControl
							type="text"
							label="Employee Name"
							v-model="form.employee_name"
							:disabled="true"
						/>
						<FormControl
							type="text"
							label="Department"
							v-model="form.department"
							:disabled="true"
						/>

						<FormControl
							type="autocomplete"
							label="Project"
							placeholder="Select Project"
							v-model="form.custom_project"
							:options="projectOptions"
						/>

						<FormControl
							type="autocomplete"
							label="Shift Type"
							v-model="form.shift_type"
							:disabled="!!props.shiftAssignmentName"
							:options="shiftTypes.data"
						/>

						<FormControl
							type="date"
							label="Start Date"
							v-model="form.start_date"
							:disabled="!!props.shiftAssignmentName"
						/>
						<FormControl
							type="date"
							label="End Date"
							v-model="form.end_date"
						/>

						<FormControl
							type="autocomplete"
							label="Shift Location"
							v-model="form.shift_location"
							:disabled="!!props.shiftAssignmentName"
							:options="shiftLocations.data"
						/>

						<FormControl
							type="select"
							:options="['Active', 'Inactive']"
							label="Status"
							v-model="form.status"
						/>

						<FormControl
							type="textarea"
							label="Note"
							v-model="form.note"
						/>

						<div v-if="!props.shiftAssignmentName && showShiftScheduleSettings" class="space-y-3">
							<FormControl
								type="select"
								:options="scheduleTypeOptions"
								label="Schedule Type"
								v-model="scheduleType"
								:disabled="!!form.shift_schedule_assignment"
							/>

							<label
								v-if="isRollingScheduleType"
								class="flex items-start gap-2 rounded border bg-gray-50 px-3 py-2 text-sm text-gray-700"
							>
								<input
									type="checkbox"
									class="mt-0.5"
									v-model="includeFlyInFlyOut"
								/>
								<span>
									<span class="block font-medium text-gray-800">Add fly in / fly out</span>
									<span class="block text-xs text-gray-500">
										Creates FI on the first day and FO on the last day of each swing.
									</span>
								</span>
							</label>
						</div>
					</div>

					<div
						v-if="(!props.shiftAssignmentName && showShiftScheduleSettings) || form.shift_schedule_assignment"
						class="mt-6 space-y-6"
					>
						<hr />
						<h4 class="font-semibold">Schedule Settings</h4>
						<div :class="scheduleType === 'Rolling Day/Night Roster' ? 'grid grid-cols-3 gap-6' : 'grid grid-cols-2 gap-6'">
							<FormControl
								v-if="scheduleType === 'Repeat On Days'"
								type="select"
								:options="['Every Week', 'Every 2 Weeks', 'Every 3 Weeks', 'Every 4 Weeks']"
								label="Frequency"
								v-model="frequency"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Rolling Roster'"
								type="number"
								label="Days On Site"
								v-model="rollingRoster.days_on_site"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Rolling Roster'"
								type="number"
								label="Days Off Site"
								v-model="rollingRoster.days_off_site"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Rolling Day/Night Roster'"
								type="number"
								label="Days On Site DS"
								v-model="rollingDayNightRoster.days_on_site_ds"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Rolling Day/Night Roster'"
								type="number"
								label="Days On Site NS"
								v-model="rollingDayNightRoster.days_on_site_ns"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Rolling Day/Night Roster'"
								type="number"
								label="Days Off Site"
								v-model="rollingDayNightRoster.days_off_site"
								:disabled="!!props.shiftAssignmentName"
							/>

							<FormControl
								v-if="scheduleType === 'Dynamic Rolling Roster'"
								type="number"
								label="Number of Rolling Rosters"
								v-model="dynamicRollingRoster.swing_count"
								:disabled="!!props.shiftAssignmentName"
							/>

							<div
								v-if="scheduleType === 'Dynamic Rolling Roster'"
								class="col-span-2 space-y-3"
							>
								<div
									v-for="(swing, index) in visibleDynamicRollingSwings"
									:key="index"
									class="rounded border bg-white p-3"
								>
									<div class="mb-3 text-sm font-medium text-gray-700">Swing {{ index + 1 }}</div>
									<div class="grid grid-cols-2 gap-6">
										<FormControl
											type="number"
											:label="`Swing ${index + 1} Days On Site`"
											v-model="swing.days_on_site"
											:disabled="!!props.shiftAssignmentName"
										/>
										<FormControl
											type="number"
											:label="`Swing ${index + 1} Days Off Site`"
											v-model="swing.days_off_site"
											:disabled="!!props.shiftAssignmentName"
										/>
									</div>
								</div>
							</div>

							<div v-if="scheduleType === 'Repeat On Days'" class="space-y-1.5">
								<div class="text-xs text-gray-600">Repeat On Days</div>
								<div class="border rounded grid grid-flow-col h-7 justify-stretch overflow-clip">
									<div
										v-for="(isSelected, day) of repeatOnDays"
										:key="day"
										class="cursor-pointer flex flex-col"
										:class="{
											'border-r': day !== 'Sunday',
											'bg-gray-100 text-gray-500': !isSelected,
											'pointer-events-none': !!props.shiftAssignmentName,
										}"
										@click="repeatOnDays[day] = !repeatOnDays[day]"
									>
										<div class="text-center text-sm my-auto">
											{{ day.substring(0, 3) }}
										</div>
									</div>
								</div>
							</div>

							<div
								v-if="isRollingScheduleType"
								:class="scheduleType === 'Rolling Day/Night Roster' ? 'col-span-3' : 'col-span-2'"
								class="rounded border bg-gray-50 px-3 py-2 text-xs text-gray-600"
							>
								<template v-if="scheduleType === 'Rolling Roster' && includeFlyInFlyOut">
									Rolling roster will create each swing using <b>FI</b> on the first day,
									the selected Shift Type for the days in between, and <b>FO</b> on the final day.
								</template>
								<template v-else-if="scheduleType === 'Rolling Roster'">
									Rolling roster will create each on-site swing using the selected Shift Type only.
									FI and FO shifts will not be created.
								</template>
								<template v-else-if="scheduleType === 'Rolling Day/Night Roster' && includeFlyInFlyOut">
									Rolling Day/Night roster will create <b>FI</b> on the first day,
									then <b>DS</b>, then <b>NS</b>, and <b>FO</b> on the final day of each swing.
								</template>
								<template v-else-if="scheduleType === 'Rolling Day/Night Roster'">
									Rolling Day/Night roster will create each swing using <b>DS</b> for the day-shift block
									and <b>NS</b> for the night-shift block. FI and FO shifts will not be created.
								</template>
								<template v-else-if="includeFlyInFlyOut">
									Dynamic rolling roster will cycle through each configured swing pattern. Each swing
									will create <b>FI</b> on the first day, the selected Shift Type for the days in between,
									and <b>FO</b> on the final day.
								</template>
								<template v-else>
									Dynamic rolling roster will cycle through each configured swing pattern and create
									each on-site day using the selected Shift Type only. FI and FO shifts will not be created.
								</template>
							</div>
						</div>
					</div>
				</div>

				<div class="border-t border-gray-200 bg-gray-50 px-6 py-4">
					<div class="flex space-x-3 justify-end">
						<Button size="md" variant="subtle" class="w-28" @click="closeDialog">
							Cancel
						</Button>
						<div v-if="props.shiftAssignmentName" class="relative">
							<Button
								size="md"
								label="Delete"
								class="w-28 text-red-600"
								@click.stop="showDeleteMenu = !showDeleteMenu"
							/>

							<div
								v-if="showDeleteMenu"
								class="absolute bottom-full right-0 z-[10050] mb-2 w-64 overflow-hidden rounded-md border border-gray-200 bg-white py-1 text-sm shadow-2xl ring-1 ring-black/5"
								@click.stop
							>
								<button
									v-for="option in actions"
									:key="option.label"
									type="button"
									class="block w-full px-3 py-2 text-left text-gray-700 transition hover:bg-gray-50 hover:text-gray-900"
									@click="runDeleteOption(option)"
								>
									{{ option.label }}
								</button>
							</div>
						</div>
						<Button
							size="md"
							variant="solid"
							:disabled="dialog.actionDisabled"
							class="w-28"
							@click="dialog.action"
						>
							{{ dialog.button }}
						</Button>
					</div>
				</div>
			</div>
		</div>

		<div
			v-if="dialogOpen && showDeleteDialog"
			class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/40 px-4"
			@click.self="showDeleteDialog = false"
		>
			<div class="w-full max-w-md overflow-hidden rounded-lg bg-white shadow-2xl" role="dialog" aria-modal="true" @click.stop>
				<div class="border-b border-gray-200 px-5 py-4">
					<h3 class="text-lg font-semibold text-gray-900">{{ deleteDialogOptions.title }}</h3>
				</div>
				<div class="px-5 py-4 text-sm text-gray-700">
					<div v-html="deleteDialogOptions.message" />
				</div>
				<div class="flex justify-end gap-2 border-t border-gray-200 bg-gray-50 px-5 py-4">
					<Button variant="subtle" @click="showDeleteDialog = false">Cancel</Button>
					<Button variant="solid" @click="confirmDelete">Confirm</Button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from "vue";
import {
	FormControl,
	Button,
	createDocumentResource,
	createResource,
	createListResource,
} from "frappe-ui";
import { dayjs, raiseToast } from "../utils";

type Status = "Active" | "Inactive";

type Selectish = string | { value: string; label?: string };
type Form = {
	[K in
		| "company"
		| "employee_name"
		| "department"
		| "employee"
		| "shift_type"
		| "shift_location"
		| "note"
		| "custom_project"]: Selectish;
} & {
	start_date: string;
	end_date: string;
	status: Status | { value: Status; label?: Status };
	shift_schedule_assignment?: string;
};

interface Props {
	modelValue?: boolean;
	isDialogOpen: boolean;
	shiftAssignmentName?: string;
	selectedCell?: { employee: string; date: string };
	employees?: { name: string; employee_name: string }[];
}

const props = withDefaults(defineProps<Props>(), { employees: () => [] });
const emit = defineEmits<{
	(e: "update:modelValue", value: boolean): void;
	(e: "fetchEvents"): void;
}>();

const formObject: Form = {
	employee: "",
	company: "",
	employee_name: "",
	department: "",
	shift_type: "",
	start_date: "",
	shift_location: "",
	note: "",
	end_date: "",
	status: "Active",
	shift_schedule_assignment: "",
	custom_project: "",
};

const repeatOnDaysObject = {
	Monday: false, Tuesday: false, Wednesday: false, Thursday: false,
	Friday: false, Saturday: false, Sunday: false,
};

const form = reactive({ ...formObject });
const repeatOnDays = reactive({ ...repeatOnDaysObject });

const shiftAssignment = ref<any>();
const selectedDate = ref<string>();
const frequency = ref("Every Week");
type ScheduleType = "Repeat On Days" | "Rolling Roster" | "Rolling Day/Night Roster" | "Dynamic Rolling Roster";
const scheduleTypeOptions: ScheduleType[] = ["Repeat On Days", "Rolling Roster", "Rolling Day/Night Roster", "Dynamic Rolling Roster"];
const scheduleType = ref<ScheduleType>("Repeat On Days");
const includeFlyInFlyOut = ref(true);
const rollingRoster = reactive({ days_on_site: 8, days_off_site: 6 });
const rollingDayNightRoster = reactive({ days_on_site_ds: 8, days_on_site_ns: 8, days_off_site: 12 });
const dynamicRollingRoster = reactive({
	swing_count: 2,
	swings: [
		{ days_on_site: 8, days_off_site: 6 },
		{ days_on_site: 4, days_off_site: 3 },
	],
});
const isRollingScheduleType = computed(() =>
	scheduleType.value === "Rolling Roster" ||
	scheduleType.value === "Rolling Day/Night Roster" ||
	scheduleType.value === "Dynamic Rolling Roster",
);
const visibleDynamicRollingSwings = computed(() => {
	const count = Math.max(1, Math.min(20, Number(dynamicRollingRoster.swing_count) || 1));
	return dynamicRollingRoster.swings.slice(0, count);
});
const showDeleteDialog = ref(false);
const showDeleteMenu = ref(false);
const deleteDialogOptions = ref<{ title: string; message: string; action: () => void }>({
	title: "",
	message: "",
	action: () => {},
});

const dialogOpen = computed({
	get: () => props.modelValue ?? props.isDialogOpen,
	set: (value: boolean) => emit("update:modelValue", value),
});

const closeDialog = () => {
	dialogOpen.value = false;
	showDeleteDialog.value = false;
	showDeleteMenu.value = false;
};

const confirmDelete = () => {
	const action = deleteDialogOptions.value.action;
	showDeleteDialog.value = false;
	showDeleteMenu.value = false;
	action();
};

const runDeleteOption = (option: { onClick?: () => void }) => {
	showDeleteMenu.value = false;
	option.onClick?.();
};

const dialog = computed(() => {
	if (props.shiftAssignmentName) {
		// compare fields to enable Update if project or end_date/status change
		const unchanged =
			form.status === shiftAssignment.value?.doc?.status &&
			form.end_date === shiftAssignment.value?.doc?.end_date &&
			form.note === shiftAssignment.value?.doc?.note &&
			getId(form.custom_project) === shiftAssignment.value?.doc?.custom_project;

		return {
			title: `[${selectedDate.value}] Shift Assignment ${props.shiftAssignmentName}`,
			button: "Update",
			action: updateShiftAssigment,
			actionDisabled: Boolean(unchanged),
		};
	}
	return { title: "New Shift Assignment", button: "Submit", action: createShiftAssigment, actionDisabled: false };
});

const actions = computed(() => {
	const options: any[] = [
		{
			label: `Shift for ${selectedDate.value}`,
			onClick: () => {
				deleteDialogOptions.value = {
					title: "Delete Shift?",
					message: `This will remove Shift Assignment: <a href='/app/shift-assignment/${props.shiftAssignmentName}' target='_blank'><u>${props.shiftAssignmentName}</u></a> scheduled for <b>${selectedDate.value}</b>.`,
					action: () => deleteCurrentShift.submit(),
				};
				showDeleteDialog.value = true;
			},
		},
		{
			label: "All Consecutive Shifts",
			onClick: () => {
				deleteDialogOptions.value = {
					title: "Delete Shift Assignment?",
					message: `This will delete Shift Assignment: <a href='/app/shift-assignment/${props.shiftAssignmentName}' target='_blank'><u>${props.shiftAssignmentName}</u></a> (scheduled from <b>${form.start_date}</b>${form.end_date ? ` to <b>${form.end_date}</b>` : ""}).`,
					action: async () => {
						await shiftAssignment.value.setValue.submit({ docstatus: 2 });
						shiftAssignments.delete.submit(props.shiftAssignmentName as string);
					},
				};
				showDeleteDialog.value = true;
			},
		},
	];
	if (form.shift_schedule_assignment)
		options.push({
			label: "Shift Schedule Assignment",
			onClick: () => {
				deleteDialogOptions.value = {
					title: "Delete Shift Schedule Assignment?",
					message: `This will delete Shift Schedule Assignment: <a href='/app/shift-schedule-assignment/${form.shift_schedule_assignment}' target='_blank'><u>${form.shift_schedule_assignment}</u></a> and all the shifts associated with it.`,
					action: () => deleteShiftScheduleAssignment.submit(),
				};
				showDeleteDialog.value = true;
			},
		});
	return options;
});

const showShiftScheduleSettings = computed(() => {
	if (!form.start_date || dayjs(form.end_date).diff(dayjs(form.start_date), "d") < 7) {
		frequency.value = "Every Week";
		if (!props.shiftAssignmentName) scheduleType.value = "Repeat On Days";
		return false;
	}
	return true;
});

const employees = computed(() =>
	props.employees.map((e) => ({ label: `${e.name}: ${e.employee_name}`, value: e.name, employee_name: e.employee_name })),
);

// --- Utils
const getId = (val: Selectish) => (val && typeof val === "object" ? (val as any).value : (val as string) || "");

// --- Watchers
watch(
	() => dialogOpen.value,
	(val) => {
		if (!val) return;
		showDeleteDialog.value = false;

		if (props.shiftAssignmentName) {
			shiftAssignment.value = getShiftAssignment(props.shiftAssignmentName);
			if (props.selectedCell) selectedDate.value = props.selectedCell.date;
		} else {
			Object.assign(form, formObject);
			scheduleType.value = "Repeat On Days";
			frequency.value = "Every Week";
			includeFlyInFlyOut.value = true;
			rollingRoster.days_on_site = 8;
			rollingRoster.days_off_site = 6;
			rollingDayNightRoster.days_on_site_ds = 8;
			rollingDayNightRoster.days_on_site_ns = 8;
			rollingDayNightRoster.days_off_site = 12;
			dynamicRollingRoster.swing_count = 2;
			dynamicRollingRoster.swings.splice(0, dynamicRollingRoster.swings.length,
				{ days_on_site: 8, days_off_site: 6 },
				{ days_on_site: 4, days_off_site: 3 },
			);
			Object.assign(repeatOnDays, repeatOnDaysObject);
			if (!props.selectedCell) return;
			form.employee = { value: props.selectedCell.employee };
			form.start_date = props.selectedCell.date;
			form.end_date = props.selectedCell.date;
		}
	},
);

watch(
	() => form.employee,
	(val) => {
		if (props.shiftAssignmentName) return;
		if (val) employee.fetch();
		else {
			form.employee_name = "";
			form.company = "";
			form.department = "";
		}
	},
);

watch(
	() => form.start_date,
	() => {
		Object.assign(repeatOnDays, repeatOnDaysObject);
		if (!form.start_date) return;
		const day = dayjs(form.start_date).format("dddd");
		repeatOnDays[day as keyof typeof repeatOnDays] = true;
	},
	{ immediate: true },
);

watch(
	() => dynamicRollingRoster.swing_count,
	() => {
		let count = Number(dynamicRollingRoster.swing_count) || 1;
		count = Math.max(1, Math.min(20, Math.floor(count)));
		dynamicRollingRoster.swing_count = count;

		while (dynamicRollingRoster.swings.length < count) {
			dynamicRollingRoster.swings.push({ days_on_site: 8, days_off_site: 6 });
		}

		if (dynamicRollingRoster.swings.length > count) {
			dynamicRollingRoster.swings.splice(count);
		}
	},
);

// --- Actions
const updateShiftAssigment = () => {
	shiftAssignment.value.setValue.submit({
		status: form.status,
		end_date: form.end_date,
		note: form.note,
		custom_project: getId(form.custom_project),
	});
};

const createShiftAssigment = () => {
	if (showShiftScheduleSettings.value && scheduleType.value === "Rolling Roster") {
		createRollingRosterAssignment.submit();
		return;
	}

	if (showShiftScheduleSettings.value && scheduleType.value === "Rolling Day/Night Roster") {
		createRollingDayNightRosterAssignment.submit();
		return;
	}

	if (showShiftScheduleSettings.value && scheduleType.value === "Dynamic Rolling Roster") {
		createDynamicRollingRosterAssignment.submit();
		return;
	}

	if (
		showShiftScheduleSettings.value &&
		(Object.values(repeatOnDays).some((day) => !day) || frequency.value !== "Every Week")
	) {
		createShiftAssignmentSchedule.submit();
	} else {
		insertShift.submit();
	}
};

// --- Resources
const getShiftAssignment = (name: string) =>
	createDocumentResource({
		doctype: "Shift Assignment",
		name,
		onSuccess: (data: Record<string, any>) => {
			Object.keys(form).forEach((k) => {
				// copy known fields if present on doc
				if (k in data) (form as any)[k] = data[k];
			});
			// coerce custom_project to { value } model if present
			if (data.custom_project) form.custom_project = { value: data.custom_project, label: data.custom_project_name || data.custom_project };
			if (form.shift_schedule_assignment) shiftSchedule.fetch();
		},
		onError(error: { messages: string[] }) {
			raiseToast("error", error.messages[0]);
		},
		setValue: {
			onSuccess() {
				raiseToast("success", "Shift Assignment updated successfully!");
				emit("fetchEvents");
			},
			onError(error: { messages: string[] }) {
				raiseToast("error", error.messages[0]);
			},
		},
	});

const employee = createResource({
	url: "verto.api.planner.get_values",
	makeParams() {
		const employee = getId(form.employee);
		return { doctype: "Employee", name: employee, fields: ["employee_name", "company", "department"] };
	},
	onSuccess: (d: { employee_name: string; company: string; department: string }) => {
		form.employee_name = d.employee_name;
		form.company = d.company;
		form.department = d.department;
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const shiftSchedule = createResource({
	url: "verto.api.planner.get_schedule_from_assignment",
	makeParams: () => ({ shift_schedule_assignment: form.shift_schedule_assignment }),
	onSuccess: (d: { frequency: string; repeat_on_days: string[] }) => {
		frequency.value = d.frequency;
		for (const day in repeatOnDays) {
			repeatOnDays[day as keyof typeof repeatOnDays] = d.repeat_on_days.includes(day);
		}
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const shiftTypes = createListResource({
	doctype: "Shift Type",
	fields: ["name"],	
	orderBy: 'name asc',
	auto: true,
	transform: (rows: { name: string }[]) => rows.map((r) => r.name),
});

const shiftLocations = createListResource({
	doctype: "Shift Location",
	fields: ["name"],
	orderBy: 'name asc',
	auto: true,
	transform: (rows: { name: string }[]) => rows.map((r) => r.name),
});

// Projects: Open only, show more than 20
const projects = createListResource({
	doctype: "Project",
	fields: ["name", "project_name"],
	filters: [["status", "=", "Open"]],
	orderBy: 'project_name asc',
	pageLength: 200, // ask for more than default
	auto: true,
});
const projectOptions = computed(() =>
	(projects.data || []).map((p: any) => ({
		label: p.project_name || p.name,
		value: p.name, // send ID
	})),
);

const shiftAssignments = createListResource({
	doctype: "Shift Assignment",
	insert: {
		onSuccess() {
			raiseToast("success", "Shift Assignment created successfully!");
			emit("fetchEvents");
		},
		onError(error: { messages: string[] }) {
			raiseToast("error", error.messages[0]);
		},
	},
	delete: {
		onSuccess() {
			raiseToast("success", "Shift Assignment deleted successfully!");
			emit("fetchEvents");
		},
		onError(error: { messages: string[] }) {
			raiseToast("error", error.messages[0]);
		},
	},
});

const insertShift = createResource({
	url: "verto.api.planner.insert_shift",
	makeParams() {
		return {
			employee: getId(form.employee),
			shift_type: getId(form.shift_type),
			shift_location: getId(form.shift_location),
			company: form.company,
			status: form.status,
			start_date: form.start_date,
			end_date: form.end_date,
			note: form.note,
			custom_project: getId(form.custom_project),
		};
	},
	onSuccess: () => {
		raiseToast("success", "Shift Assignment created successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const deleteCurrentShift = createResource({
	url: "verto.api.planner.break_shift",
	makeParams: () => ({ assignment: props.shiftAssignmentName, date: selectedDate.value }),
	onSuccess: () => {
		raiseToast("success", "Shift deleted successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const createShiftAssignmentSchedule = createResource({
	url: "verto.api.planner.create_shift_schedule_assignment",
	makeParams() {
		return {
			employee: getId(form.employee),
			shift_type: getId(form.shift_type),
			company: form.company,
			status: form.status,
			start_date: form.start_date,
			end_date: form.end_date,
			note: form.note,
			shift_location: getId(form.shift_location),
			repeat_on_days: Object.keys(repeatOnDays).filter((d) => repeatOnDays[d as keyof typeof repeatOnDays]),
			frequency: frequency.value,
			custom_project: getId(form.custom_project),
		};
	},
	onSuccess: () => {
		raiseToast("success", "Shift Schedule Assignment created successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const createRollingRosterAssignment = createResource({
	url: "verto.api.planner.create_rolling_roster_assignment",
	makeParams() {
		return {
			employee: getId(form.employee),
			shift_type: getId(form.shift_type),
			company: form.company,
			status: form.status,
			start_date: form.start_date,
			end_date: form.end_date,
			note: form.note,
			shift_location: getId(form.shift_location),
			custom_project: getId(form.custom_project),
			days_on_site: rollingRoster.days_on_site,
			days_off_site: rollingRoster.days_off_site,
			include_fly_in_out: includeFlyInFlyOut.value,
		};
	},
	onSuccess: () => {
		raiseToast("success", "Rolling Roster created successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const createRollingDayNightRosterAssignment = createResource({
	url: "verto.api.planner.create_rolling_day_night_roster_assignment",
	makeParams() {
		return {
			employee: getId(form.employee),
			company: form.company,
			status: form.status,
			start_date: form.start_date,
			end_date: form.end_date,
			note: form.note,
			shift_location: getId(form.shift_location),
			custom_project: getId(form.custom_project),
			days_on_site_ds: rollingDayNightRoster.days_on_site_ds,
			days_on_site_ns: rollingDayNightRoster.days_on_site_ns,
			days_off_site: rollingDayNightRoster.days_off_site,
			include_fly_in_out: includeFlyInFlyOut.value,
			day_shift_type: "DS",
			night_shift_type: "NS",
		};
	},
	onSuccess: () => {
		raiseToast("success", "Rolling Day/Night Roster created successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const createDynamicRollingRosterAssignment = createResource({
	url: "verto.api.planner.create_dynamic_rolling_roster_assignment",
	makeParams() {
		return {
			employee: getId(form.employee),
			shift_type: getId(form.shift_type),
			company: form.company,
			status: form.status,
			start_date: form.start_date,
			end_date: form.end_date,
			note: form.note,
			shift_location: getId(form.shift_location),
			custom_project: getId(form.custom_project),
			roster_segments: visibleDynamicRollingSwings.value.map((swing) => ({
				days_on_site: swing.days_on_site,
				days_off_site: swing.days_off_site,
			})),
			include_fly_in_out: includeFlyInFlyOut.value,
		};
	},
	onSuccess: () => {
		raiseToast("success", "Dynamic Rolling Roster created successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});

const deleteShiftScheduleAssignment = createResource({
	url: "verto.api.planner.delete_shift_schedule_assignment",
	makeParams: () => ({ shift_schedule_assignment: form.shift_schedule_assignment }),
	onSuccess: () => {
		raiseToast("success", "Shift Schedule Assignment deleted successfully!");
		emit("fetchEvents");
	},
	onError(error: { messages: string[] }) {
		raiseToast("error", error.messages[0]);
	},
});
</script>
