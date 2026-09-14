<template>
  <div class="flex flex-wrap items-end gap-3">
    <!-- Period Change -->
    <div class="flex items-center bg-gray-50 rounded-5 space-x-0.5">
      <Button
        icon="lucide-chevron-left"
        aria-label="Previous period"
        variant="ghost"
        @click="goToPreviousPeriod"
      />
      <span class="w-36 text-center text-base-medium">
        {{ periodLabel }}
      </span>
      <Button
        icon="lucide-chevron-right"
        aria-label="Next period"
        variant="ghost"
        @click="goToNextPeriod"
      />
    </div>

    <!-- Availability range -->
    <div class="ml-4">
      <DateRangePicker
        v-model="dateRangeValue"
        label="Availability"
        variant="subtle"
        placeholder="View Availability"
      />
    </div>
    <!-- Filters -->
    <div class="ml-auto flex flex-wrap items-end gap-2.5">
      <div
        v-for="[key, value] of Object.entries(filters)"
        :key="key"
        class="w-40"
      >
        <Combobox
          :label="toTitleCase(key)"
          :placeholder="toTitleCase(key)"
          :options="value.options"
          v-model="value.model"
          :disabled="!value.options.length"
        />
      </div>
      <Button
        aria-label="Clear filters"
        icon="lucide-x"
        @click="Object.values(filters).forEach((d) => (d.model = null))"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  Combobox,
  DateRangePicker,
  Button,
  createResource,
  createListResource,
} from "frappe-ui";
import type { Dayjs } from "dayjs";
import { raiseToast } from "../utils";

export type FilterField =
  | "company"
  | "department"
  | "branch"
  | "designation"
  | "shift_type"
  | "shift_location";

type ViewMode = "month" | "year";

const props = withDefaults(
  defineProps<{ firstOfMonth: Dayjs; viewMode?: ViewMode }>(),
  {
    viewMode: "month",
  },
);
const emit = defineEmits<{
  (e: "addToMonth", change: number): void;
  (e: "updateFilters", newFilters: { [K in FilterField]: string }): void;
  (
    e: "updateDateRange",
    payload: { from: string | null; to: string | null },
  ): void;
  (e: "updateProjectShiftsFilled", value: 0 | 1): void;
}>();

const periodLabel = computed(() => {
  if (props.viewMode === "year") return props.firstOfMonth.format("YYYY");
  return `${props.firstOfMonth.format("MMMM")}, ${props.firstOfMonth.format("YYYY")}`;
});

function goToPreviousPeriod() {
  emit("addToMonth", props.viewMode === "year" ? -12 : -1);
}

function goToNextPeriod() {
  emit("addToMonth", props.viewMode === "year" ? 12 : 1);
}

/** Date range model (support string/object/array from different frappe-ui builds) */
const dateRangeValue = ref<string[]>([]);
function normalizeRange(v: string[]) {
  return { from: v?.[0] || null, to: v?.[1] || null };
}

/** Filters */
const filters: {
  [K in FilterField]: {
    options: string[];
    model?: string | null;
  };
} = reactive({
  company: { options: [], model: null },
  department: { options: [], model: null },
  branch: { options: [], model: null },
  designation: { options: [], model: null },
  shift_type: { options: [], model: null },
  shift_location: { options: [], model: null },
});

watch(
  () => filters.company.model,
  (val) => {
    if (val) getFilterOptions("department", { company: val });
    else {
      filters.department.model = null;
      filters.department.options = [];
    }
  },
);

watch(filters, (val) => {
  const newFilters = {
    company: val.company.model || "",
    department: val.department.model || "",
    branch: val.branch.model || "",
    designation: val.designation.model || "",
    shift_type: val.shift_type.model || "",
    shift_location: val.shift_location.model || "",
  };
  emit("updateFilters", newFilters);
});

watch(
  dateRangeValue,
  (val) => {
    const { from, to } = normalizeRange(val);
    if (!from || !to) {
      emit("updateDateRange", { from: null, to: null });
      return;
    }
    let a = from,
      b = to;
    if (a > b) [a, b] = [b, a];
    emit("updateDateRange", { from: a, to: b });
  },
  { deep: true },
);

const toTitleCase = (str: string) =>
  str
    .split("_")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");

const defaultCompany = createResource({
  url: "verto.api.planner.get_default_company",
  auto: true,
  onSuccess: () => {
    [
      "company",
      "branch",
      "designation",
      "shift_type",
      "shift_location",
    ].forEach((field) => getFilterOptions(field as FilterField));
  },
});

const getFilterOptions = (
  field: FilterField,
  listFilters: { company?: string } = {},
) => {
  createListResource({
    doctype: toTitleCase(field),
    fields: ["name"],
    filters: listFilters,
    pageLength: 100,
    auto: true,
    onSuccess: (data: { name: string }[]) => {
      const value = field === "company" ? defaultCompany.data : "";
      filters[field].model = value;
      filters[field].options = data.map((item) => item.name);
    },
    onError(error: { messages: string[] }) {
      raiseToast("error", error.messages[0]);
    },
  });
};
</script>
