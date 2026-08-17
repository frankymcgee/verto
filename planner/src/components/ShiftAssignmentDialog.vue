<template>
	<Teleport to="body">
		<div
			v-if="dialogOpen"
			class="fixed inset-0 bg-black/50"
			style="z-index: 2147483000"
			@click.self="closeDialog"
		/>

		<div
			v-if="dialogOpen"
			class="fixed inset-0 flex items-start justify-center overflow-y-auto px-4 py-10"
			style="z-index: 2147483100"
			@click.self="closeDialog"
		>
			<div
				class="planner-shift-assignment-dialog w-full max-w-5xl overflow-visible rounded-lg bg-white shadow-2xl"
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

				<div class="planner-shift-assignment-dialog-body overflow-visible px-6 py-5">
					<div class="grid grid-cols-2 gap-6">
						<div class="planner-native-field">
							<label class="planner-native-label">Employee</label>
							<select
								v-model="form.employee"
								:disabled="!!props.shiftAssignmentName"
								class="planner-native-control"
							>
								<option value="">Select Employee</option>
								<option
									v-for="option in employees"
									:key="option.value"
									:value="option.value"
								>
									{{ option.label }}
								</option>
							</select>
						</div>
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

						<div class="planner-native-field">
							<label class="planner-native-label">Project</label>
							<select v-model="form.custom_project" class="planner-native-control">
								<option value="">Select Project</option>
								<option
									v-for="option in projectOptions"
									:key="option.value"
									:value="option.value"
								>
									{{ option.label }}
								</option>
							</select>
						</div>

						<div class="planner-native-field">
							<label class="planner-native-label">Shift Type</label>
							<select
								v-model="form.shift_type"
								:disabled="!!props.shiftAssignmentName"
								class="planner-native-control"
							>
								<option value="">Select Shift Type</option>
								<option v-for="shiftType in (shiftTypes.data || [])" :key="shiftType" :value="shiftType">
									{{ shiftType }}
								</option>
							</select>
						</div>

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

						<div class="planner-native-field">
							<label class="planner-native-label">Shift Location</label>
							<select
								v-model="form.shift_location"
								:disabled="!!props.shiftAssignmentName"
								class="planner-native-control"
							>
								<option value="">Select Shift Location</option>
								<option v-for="location in (shiftLocations.data || [])" :key="location" :value="location">
									{{ location }}
								</option>
							</select>
						</div>

						<div class="planner-native-field">
							<label class="planner-native-label">Status</label>
							<select v-model="form.status" class="planner-native-control">
								<option value="Active">Active</option>
								<option value="Inactive">Inactive</option>
							</select>
						</div>

						<FormControl
							type="textarea"
							label="Note"
							v-model="form.note"
						/>

						<div v-if="!props.shiftAssignmentName && showShiftScheduleSettings" class="space-y-3">
							<div class="planner-native-field">
								<label class="planner-native-label">Schedule Type</label>
								<select
									v-model="scheduleType"
									:disabled="!!form.shift_schedule_assignment"
									class="planner-native-control"
								>
									<option v-for="option in scheduleTypeOptions" :key="option" :value="option">{{ option }}</option>
								</select>
							</div>

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
								<div v-if="scheduleType === 'Repeat On Days'" class="planner-native-field">
									<label class="planner-native-label">Frequency</label>
									<select
										v-model="frequency"
										:disabled="!!props.shiftAssignmentName"
										class="planner-native-control"
									>
										<option value="Every Week">Every Week</option>
										<option value="Every 2 Weeks">Every 2 Weeks</option>
										<option value="Every 3 Weeks">Every 3 Weeks</option>
										<option value="Every 4 Weeks">Every 4 Weeks</option>
									</select>
								</div>

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
								class="absolute bottom-full right-0 mb-2 w-64 overflow-hidden rounded-md border border-gray-200 bg-white py-1 text-sm shadow-2xl ring-1 ring-black/5"
								style="z-index: 2147483400"
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
			class="fixed inset-0 flex items-center justify-center bg-black/40 px-4"
			style="z-index: 2147483300"
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
import { reactive, ref, computed, watch, onBeforeUnmount } from "vue";
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

const setDialogBodyClass = (isOpen: boolean) => {
	if (typeof document === "undefined") return;
	document.body.classList.toggle("planner-shift-assignment-dialog-open", isOpen);
};

watch(
	() => dialogOpen.value,
	(value) => setDialogBodyClass(value),
	{ immediate: true },
);

onBeforeUnmount(() => setDialogBodyClass(false));

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
			form.employee = props.selectedCell.employee;
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
			// native selects use plain string values
			form.employee = data.employee || "";
			form.shift_type = data.shift_type || "";
			form.shift_location = data.shift_location || "";
			form.custom_project = data.custom_project || "";
			form.status = data.status || "Active";
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

<style>
/*
	Shift Assignment uses a fullscreen modal, but Frappe UI select/autocomplete menus
	can render either inside the field wrapper or through a body-level portal.
	This z-index block handles both cases while the dialog is open.
*/
body.planner-shift-assignment-dialog-open {
	--planner-shift-dialog-z: 2147483100;
	--planner-shift-field-z: 2147483400;
}

.planner-shift-assignment-dialog,
.planner-shift-assignment-dialog * {
	overflow-anchor: none;
}

.planner-shift-assignment-dialog {
	isolation: isolate;
	overflow: visible !important;
}

.planner-shift-assignment-dialog-body,
.planner-shift-assignment-dialog-body *,
.planner-shift-assignment-dialog .grid,
.planner-shift-assignment-dialog .grid > * {
	overflow: visible !important;
}

/* Raise whichever field is actively open so its option panel is above nearby fields. */
.planner-shift-assignment-dialog .grid > *,
.planner-shift-assignment-dialog .space-y-3 > *,
.planner-shift-assignment-dialog .space-y-6 > *,
.planner-shift-assignment-dialog .rounded.border.bg-white,
.planner-shift-assignment-dialog .rounded.border.bg-white * {
	position: relative;
	z-index: 1;
}

.planner-shift-assignment-dialog .grid > *:focus-within,
.planner-shift-assignment-dialog .space-y-3 > *:focus-within,
.planner-shift-assignment-dialog .space-y-6 > *:focus-within,
.planner-shift-assignment-dialog .rounded.border.bg-white:focus-within {
	z-index: var(--planner-shift-field-z) !important;
}

/* Panels rendered inside the dialog. */
.planner-shift-assignment-dialog [role="listbox"],
.planner-shift-assignment-dialog [role="menu"],
.planner-shift-assignment-dialog [data-headlessui-state],
.planner-shift-assignment-dialog [data-popper-placement],
.planner-shift-assignment-dialog [id^="headlessui-"],
.planner-shift-assignment-dialog .dropdown-menu,
.planner-shift-assignment-dialog .popover,
.planner-shift-assignment-dialog .frappe-ui-popover,
.planner-shift-assignment-dialog .frappe-ui-dropdown,
.planner-shift-assignment-dialog .awesomplete > ul,
.planner-shift-assignment-dialog .autocomplete-results,
.planner-shift-assignment-dialog .absolute {
	z-index: var(--planner-shift-field-z) !important;
}

/* Panels rendered through a body-level portal by Frappe UI / Headless UI. */
body.planner-shift-assignment-dialog-open > [role="listbox"],
body.planner-shift-assignment-dialog-open > [role="menu"],
body.planner-shift-assignment-dialog-open > [data-headlessui-state],
body.planner-shift-assignment-dialog-open > [data-popper-placement],
body.planner-shift-assignment-dialog-open > [id^="headlessui-"],
body.planner-shift-assignment-dialog-open .headlessui-portal-root,
body.planner-shift-assignment-dialog-open .headlessui-portal-root *,
body.planner-shift-assignment-dialog-open .frappe-ui-popover,
body.planner-shift-assignment-dialog-open .frappe-ui-dropdown,
body.planner-shift-assignment-dialog-open .dropdown-menu,
body.planner-shift-assignment-dialog-open .popover,
body.planner-shift-assignment-dialog-open .awesomplete > ul,
body.planner-shift-assignment-dialog-open .autocomplete-results {
	z-index: var(--planner-shift-field-z) !important;
}

.planner-native-field {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.planner-native-label {
	font-size: 0.875rem;
	font-weight: 500;
	line-height: 1.25rem;
	color: rgb(55 65 81);
}

.planner-native-control {
	width: 100%;
	height: 2.25rem;
	border-radius: 0.375rem;
	border: 1px solid rgb(209 213 219);
	background-color: #fff;
	padding: 0.375rem 0.75rem;
	font-size: 0.875rem;
	line-height: 1.25rem;
	color: rgb(17 24 39);
	outline: none;
}

.planner-native-control:focus {
	border-color: rgb(99 102 241);
	box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.planner-native-control:disabled {
	cursor: not-allowed;
	background-color: rgb(249 250 251);
	color: rgb(107 114 128);
}

</style>
