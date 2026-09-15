import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises, DOMWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { createRouter, createMemoryHistory } from "vue-router";
import { FormControl, Combobox, Select, dialog, setConfig } from "frappe-ui";
import ShiftAssignmentDialog from "../src/components/ShiftAssignmentDialog.vue";
import ProjectSpanDialog from "../src/components/ProjectSpanDialog.vue";
import YearViewTable from "../src/components/YearViewTable.vue";
import { dayjs } from "../src/utils";

vi.mock("../src/utils", async () => ({
  ...(await vi.importActual("../src/utils")),
  raiseToast: vi.fn(),
}));

const employees = [
  { name: "EMP-1", employee_name: "Alex", company: "Test company" },
];
const defaults = {
  custom_project: "PROJ-1",
  project_name: "Test project",
  shift_location: "LOC-1",
  shift_type: "DS",
  start_date: "2026-09-01",
  end_date: "2026-09-30",
};
let wrapper, saved, project, shiftDoc;
const settle = async () => {
  await flushPromises();
  await nextTick();
};
const projectDetails = () => ({
  ...project,
  project_start_date: project.start_date,
  project_end_date: project.end_date,
  can_update_project_dates: true,
  can_update_notes: true,
  notes_field: "notes",
  notes: "Original note",
  execution_tasks: [
    {
      name: "TASK-1",
      subject: "Execution Works",
      location_subject: "General",
      can_assign: true,
      assignees: [],
    },
  ],
});

describe('Live project collaboration', () => {
  it('preserves unsaved notes, blocks stale saves, and lets the user reload', async () => {
    let details = { ...projectDetails(), modified: 'revision-one' };
    setConfig('resourceFetcher', async ({ url }) => {
      if (url.endsWith('get_project_planner_details')) return structuredClone(details);
      throw new Error(`Unexpected request: ${url}`);
    });
    await mountComponent(ProjectSpanDialog, { isDialogOpen: true, modelValue: true, project });
    const notes = () => new DOMWrapper(document.querySelector('textarea[placeholder="Add project notes..."]'));
    await notes().setValue('My unsaved note');
    details = { ...details, modified: 'revision-two', notes: 'Saved by another planner' };
    await wrapper.vm.refreshLive();
    await settle();
    expect(notes().element.value).toBe('My unsaved note');
    expect(document.body.textContent).toContain('This project changed elsewhere');
    expect(button('Update').attributes('disabled')).toBeDefined();
    await button('Discard my edits and reload').trigger('click');
    await settle();
    expect(notes().element.value).toBe('Saved by another planner');
    expect(button('Update').attributes('disabled')).toBeUndefined();
  });

  it('updates a clean open form live and sends the latest revision when saving', async () => {
    let details = { ...projectDetails(), modified: 'revision-one' };
    let submitted;
    setConfig('resourceFetcher', async ({ url, params }) => {
      if (url.endsWith('get_project_planner_details')) return structuredClone(details);
      if (url.endsWith('update_project_planner_details')) { submitted = params; return structuredClone(details); }
      throw new Error(`Unexpected request: ${url}`);
    });
    await mountComponent(ProjectSpanDialog, { isDialogOpen: true, modelValue: true, project });
    details = { ...details, modified: 'revision-two', notes: 'Latest saved note' };
    await wrapper.vm.refreshLive();
    await settle();
    expect(document.querySelector('textarea[placeholder="Add project notes..."]').value).toBe('Latest saved note');
    await button('Update').trigger('click');
    await settle();
    expect(submitted.expected_modified).toBe('revision-two');
  });
});
const shiftModal = () =>
  document
    .querySelector(".planner-shift-assignment-dialog-body")
    ?.closest("[role=dialog]") || null;
function picker(label) {
  return [
    ...wrapper.findAllComponents(Combobox),
    ...wrapper.findAllComponents(Select),
  ].find((c) => c.props("label") === label);
}
async function selectValue(label, value) {
  picker(label).vm.$emit("update:modelValue", value);
  await settle();
}
function button(label, root = document) {
  return new DOMWrapper(
    [...root.querySelectorAll("button")].find(
      (el) => el.textContent.trim() === label,
    ),
  );
}
async function fieldValue(label, value) {
  const control = wrapper
    .findAllComponents(FormControl)
    .find((control) => control.props("label") === label);
  await control.find("input").setValue(value);
  await control.find("input").trigger("blur");
}
async function mountComponent(component, props) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: { template: "<div />" } }],
  });
  await router.push("/");
  await router.isReady();
  wrapper = mount(component, {
    attachTo: document.body,
    props,
    global: { plugins: [router] },
  });
  await settle();
}
async function openShift(extra = {}) {
  await mountComponent(ShiftAssignmentDialog, {
    isDialogOpen: false,
    modelValue: false,
    employees,
    assignmentDefaults: defaults,
    ...extra,
  });
  await wrapper.setProps({ isDialogOpen: true, modelValue: true });
  await settle();
}
async function chooseEmployeeAndDates(end = "2026-09-15") {
  await selectValue("Employee", "EMP-1");
  await settle();
  await fieldValue("Start Date", "2026-09-14");
  await fieldValue("End Date", end);
  await settle();
}

beforeEach(() => {
  saved = [];
  project = {
    project: "PROJ-1",
    project_name: "Test project",
    customer: "Test customer",
    custom_project_location: "LOC-1",
    start_date: "2026-09-01",
    end_date: "2026-09-30",
    status: "Open",
    task_count: 3,
    has_tasks: true,
    is_active: true,
    po_entered: true,
    assignments: {},
    ds_personnel: [],
    ns_personnel: [],
    ds_requested: 2,
    ns_requested: 2,
  };
  shiftDoc = {
    name: "SHIFT-1",
    employee: "EMP-1",
    employee_name: "Alex",
    company: "Test company",
    department: "Maintenance",
    custom_project: "OTHER-PROJECT",
    shift_type: "NS",
    shift_location: "OTHER-LOCATION",
    start_date: "2026-10-01",
    end_date: "2026-10-02",
    status: "Active",
  };
  setConfig("resourceFetcher", async ({ url, params }) => {
    if (url.endsWith('get_bootstrap')) return {
      references: { shift_type: [{ name: 'DS' }, { name: 'NS' }],
        shift_location: [{ name: 'LOC-1' }, { name: 'OTHER-LOCATION' }] },
      projects: [{ name: 'OTHER-PROJECT', project_name: 'Other project' }],
    };
    if (url === "frappe.client.get_list") {
      if (params.doctype === "Shift Type")
        return [{ name: "DS" }, { name: "NS" }];
      if (params.doctype === "Shift Location")
        return [{ name: "LOC-1" }, { name: "OTHER-LOCATION" }];
      if (params.doctype === "Project")
        return [{ name: "OTHER-PROJECT", project_name: "Other project" }]; // source project deliberately outside the list
      if (params.doctype === "Shift Assignment") return [];
    }
    if (url === "frappe.client.get") return shiftDoc;
    if (url.endsWith("get_values"))
      return {
        employee_name: "Alex",
        company: "Test company",
        department: "Maintenance",
      };
    if (url.endsWith("get_project_planner_details")) return projectDetails();
    if (url.endsWith("get_year_events"))
      return {
        contract_version: 2,
        employee_event_days: {},
        project_rows: [{ ...project }],
        day_markers: {},
        employee_details: {},
        timesheet_days: {},
      };
    if (url.endsWith("insert_shift") || url.includes("create_")) {
      saved.push({ url, params });
      project = {
        ...project,
        ds_personnel: params.shift_type === "DS" ? ["Alex"] : [],
        ns_personnel: params.shift_type === "NS" ? ["Alex"] : [],
      };
      return {};
    }
    throw new Error(
      `Unexpected fixture request ${url} ${JSON.stringify(params)}`,
    );
  });
});
afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("Project shift defaults", () => {
  it.each(["DS", "NS"])(
    "emits the actual project and location from the %s section",
    async (shift) => {
      await mountComponent(ProjectSpanDialog, {
        isDialogOpen: true,
        modelValue: true,
        project,
      });
      const name = shift === "DS" ? "Assign day shifts" : "Assign night shifts";
      for (const label of ["Project Start Date", "Project End Date"]) {
        expect(
          wrapper
            .findAllComponents(FormControl)
            .find((c) => c.props("label") === label)
            .find("input").element.disabled,
        ).toBe(false);
      }
      await new DOMWrapper(
        document.querySelector(`[aria-label="${name}"]`),
      ).trigger("click");
      expect(wrapper.emitted("assignShifts")[0][0]).toEqual({
        ...defaults,
        shift_type: shift,
      });
      expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    },
  );

  it.each(["DS", "NS"])(
    "prefills %s including project dates and leaves personnel for entry",
    async (shift) => {
      await openShift({
        assignmentDefaults: { ...defaults, shift_type: shift },
        selectedCell: { employee: "STALE-EMPLOYEE", date: "2025-01-01" },
      });
      expect(picker("Project").props("modelValue")).toBe("PROJ-1");
      expect(picker("Shift Type").props("modelValue")).toBe(shift);
      expect(picker("Shift Location").props("modelValue")).toBe("LOC-1");
      expect(picker("Employee").props("modelValue")).toBe("");
      expect(
        wrapper
          .findAllComponents(FormControl)
          .find((c) => c.props("label") === "Start Date")
          .find("input").element.value,
      ).toBe(defaults.start_date);
      expect(
        wrapper
          .findAllComponents(FormControl)
          .find((c) => c.props("label") === "End Date")
          .find("input").element.value,
      ).toBe(defaults.end_date);
      expect(saved).toEqual([]);
    },
  );

  it("selects employees and shift types through the v1 popup controls", async () => {
    await openShift();
    await picker("Employee").find("input").trigger("click");
    await settle();
    const employeeOption = [...document.querySelectorAll("[role=option]")].find(
      (el) => el.textContent.includes("Alex"),
    );
    expect(employeeOption).toBeTruthy();
    await new DOMWrapper(employeeOption).trigger("click");
    await settle();
    expect(picker("Employee").props("modelValue")).toBe("EMP-1");
    const trigger = picker("Shift Type").find("[role=combobox]");
    await trigger.trigger("keydown", { key: "Enter" });
    await settle();
    const nightOption = [...document.querySelectorAll("[role=option]")].find(
      (el) => el.textContent.trim() === "NS",
    );
    expect(nightOption).toBeTruthy();
    await new DOMWrapper(nightOption).trigger("keydown", {key: "Enter"});
    await settle();
    expect(picker("Shift Type").props("modelValue")).toBe("NS");
  });

  it("displays the project and linked location even outside the fetched options", async () => {
    await openShift({
      assignmentDefaults: { ...defaults, shift_location: "REMOTE-LOCATION" },
    });
    expect(
      picker("Project")
        .props("options")
        .find((o) => o.value === "PROJ-1").label,
    ).toBe("Test project");
    expect(picker("Shift Location").props("modelValue")).toBe(
      "REMOTE-LOCATION",
    );
  });

  it("allows the location to be selected when the project has none", async () => {
    await openShift({
      assignmentDefaults: { ...defaults, shift_location: "" },
    });
    expect(picker("Shift Location").props("modelValue")).toBe("");
    expect(Boolean(picker("Shift Location").props("disabled"))).toBe(false);
    await selectValue("Shift Location", "LOC-1");
    expect(picker("Shift Location").props("modelValue")).toBe("LOC-1");
  });

  it("resets defaults before a normal calendar assignment", async () => {
    await openShift();
    await wrapper.setProps({ modelValue: false, isDialogOpen: false });
    await wrapper.setProps({
      assignmentDefaults: null,
      selectedCell: { employee: "EMP-1", date: "2026-10-14" },
      modelValue: true,
      isDialogOpen: true,
    });
    await settle();
    expect(picker("Employee").props("modelValue")).toBe("EMP-1");
    expect(picker("Project").props("modelValue")).toBe("");
    expect(picker("Shift Type").props("modelValue")).toBe("");
    expect(picker("Shift Location").props("modelValue")).toBe("");
    expect(
      wrapper
        .findAllComponents(FormControl)
        .find((c) => c.props("label") === "Start Date")
        .find("input").element.value,
    ).toBe("2026-10-14");
  });

  it("keeps an existing shift document values when editing", async () => {
    await openShift({
      shiftAssignmentName: "SHIFT-1",
      selectedCell: { employee: "EMP-1", date: "2026-10-01" },
    });
    expect(picker("Project").props("modelValue")).toBe("OTHER-PROJECT");
    expect(picker("Shift Type").props("modelValue")).toBe("NS");
    expect(picker("Shift Location").props("modelValue")).toBe("OTHER-LOCATION");
    expect(Boolean(picker("Shift Type").props("disabled"))).toBe(true);
  });
});

describe("Submitting project shifts", () => {
  it.each(["DS", "NS"])(
    "passes project defaults into a single %s assignment",
    async (shift) => {
      await openShift({
        assignmentDefaults: { ...defaults, shift_type: shift },
      });
      await chooseEmployeeAndDates();
      await button("Submit", shiftModal()).trigger("click");
      await settle();
      expect(saved[0].url).toBe("verto.api.planner.insert_shift");
      expect(saved[0].params).toMatchObject({
        custom_project: "PROJ-1",
        shift_location: "LOC-1",
        shift_type: shift,
        employee: "EMP-1",
        company: "Test company",
      });
      expect(wrapper.emitted("fetchEvents")).toHaveLength(1);
    },
  );

  it.each([
    ["Repeat On Days", "create_shift_schedule_assignment"],
    ["Rolling Roster", "create_rolling_roster_assignment"],
    ["Dynamic Rolling Roster", "create_dynamic_rolling_roster_assignment"],
    ["Rolling Day/Night Roster", "create_rolling_day_night_roster_assignment"],
  ])("retains defaults with the %s option", async (schedule, method) => {
    await openShift();
    await chooseEmployeeAndDates("2026-10-30");
    await selectValue("Schedule Type", schedule);
    if (schedule === "Rolling Roster") await fieldValue("Days On Site", 4);
    await button("Submit", shiftModal()).trigger("click");
    await settle();
    expect(saved[0].url).toBe(`verto.api.planner.${method}`);
    expect(saved[0].params).toMatchObject({
      custom_project: "PROJ-1",
      shift_location: "LOC-1",
      employee: "EMP-1",
    });
    if (schedule === "Rolling Roster")
      expect(saved[0].params.days_on_site).toBe("4");
    if (schedule !== "Rolling Day/Night Roster")
      expect(saved[0].params.shift_type).toBe("DS");
    else
      expect(saved[0].params).toMatchObject({
        day_shift_type: "DS",
        night_shift_type: "NS",
      });
  });
});

describe("Annual Planner integration", () => {
  async function openProject() {
    await mountComponent(YearViewTable, {
      firstOfMonth: dayjs("2026-09-01"),
      employees,
      employeeFilters: {},
      shiftFilters: {},
    });
    await wrapper.find(".year-project-cell.year-project-span").trigger("click");
    await settle();
    expect(
      document.querySelector('[aria-label="Assign day shifts"]'),
    ).not.toBeNull();
  }
  it("returns to project details on cancel without assigning a shift", async () => {
    await openProject();
    await new DOMWrapper(
      document.querySelector('[aria-label="Assign night shifts"]'),
    ).trigger("click");
    await settle();
    expect(picker("Shift Type").props("modelValue")).toBe("NS");
    expect(
      wrapper
        .findAllComponents(FormControl)
        .find((c) => c.props("label") === "Start Date")
        .find("input").element.value,
    ).toBe(defaults.start_date);
    expect(
      wrapper
        .findAllComponents(FormControl)
        .find((c) => c.props("label") === "End Date")
        .find("input").element.value,
    ).toBe(defaults.end_date);
    expect(
      document.querySelector('[aria-label="Assign day shifts"]'),
    ).toBeNull();
    await new DOMWrapper(
      shiftModal().querySelector('[aria-label="Close"]'),
    ).trigger("click");
    await settle();
    expect(
      document.querySelector('[aria-label="Assign day shifts"]'),
    ).not.toBeNull();
    expect(shiftModal()).toBeNull();
    expect(saved).toEqual([]);
  });

  it("refreshes DS personnel while retaining unsaved project notes", async () => {
    await openProject();
    const notes = new DOMWrapper(
      document.querySelector('textarea[placeholder="Add project notes..."]'),
    );
    await notes.setValue("Keep this unsaved note");
    await new DOMWrapper(
      document.querySelector('[aria-label="Assign day shifts"]'),
    ).trigger("click");
    await settle();
    await chooseEmployeeAndDates();
    await button("Submit", shiftModal()).trigger("click");
    await settle();
    expect(shiftModal()).toBeNull();
    expect(
      wrapper.findComponent(ProjectSpanDialog).props("project").ds_personnel,
    ).toEqual(["Alex"]);
    expect(
      document.querySelector('textarea[placeholder="Add project notes..."]')
        .value,
    ).toBe("Keep this unsaved note");
    expect(document.body.textContent).toContain("Alex");
  });
});

describe("Appending generic tasks", () => {
  it("keeps existing personnel controls and allows repeated additions", async () => {
    let details = { ...projectDetails(), can_create_generic_tasks: true };
    const confirm = vi
      .spyOn(dialog, "confirm")
      .mockImplementation((options) => options.onConfirm());
    setConfig("resourceFetcher", async ({ url, params }) => {
      if (url.endsWith("get_project_planner_details")) return details;
      if (url.endsWith("create_generic_project_tasks")) {
        saved.push(params);
        details = {
          ...details,
          task_count: details.task_count + 3,
          execution_tasks: [
            ...details.execution_tasks,
            {
              name: `NEW-${saved.length}`,
              subject: `New Execution ${saved.length}`,
              location_subject: "General",
              can_assign: true,
              assignees: [],
            },
          ],
        };
        return { project_details: details, created_tasks: [{}, {}, {}] };
      }
      throw new Error(`Unexpected request ${url}`);
    });
    await mountComponent(ProjectSpanDialog, {
      isDialogOpen: true,
      modelValue: true,
      project,
    });
    expect(
      document.querySelector(
        '[aria-label="Manage personnel for Execution Works"]',
      ),
    ).not.toBeNull();
    for (let i = 1; i <= 2; i++) {
      expect(button("Add 3 Generic Tasks").element.disabled).toBe(false);
      await button("Add 3 Generic Tasks").trigger("click");
      await settle();
      expect(
        document.querySelector(
          `[aria-label="Manage personnel for New Execution ${i}"]`,
        ),
      ).not.toBeNull();
      expect(
        document.querySelector(
          '[aria-label="Manage personnel for Execution Works"]',
        ),
      ).not.toBeNull();
    }
    expect(saved).toHaveLength(2);
    expect(saved[0]).toMatchObject({
      project: "PROJ-1",
      locations: [{ subject: "General", work_summaries: ["Execution Works"] }],
    });
    expect(wrapper.emitted("fetchEvents")).toHaveLength(2);
    expect(confirm.mock.calls[0][0].message).toContain(
      "Existing tasks will be preserved",
    );
  });
});

describe("Location Work Summaries", () => {
  it.each([false, true])(
    "adds multiple summaries with existing location=%s",
    async (existing) => {
      const details = {
        ...projectDetails(),
        can_create_generic_tasks: true,
        location_tasks: [{ name: "LOCATION-1", subject: "Area A" }],
      };
      vi.spyOn(dialog, "confirm").mockImplementation((options) =>
        options.onConfirm(),
      );
      setConfig("resourceFetcher", async ({ url, params }) => {
        if (url.endsWith("get_project_planner_details")) return details;
        if (url.endsWith("create_generic_project_tasks")) {
          saved.push(params);
          return { project_details: details, created_tasks: [{}, {}] };
        }
        throw new Error(`Unexpected ${url}`);
      });
      await mountComponent(ProjectSpanDialog, {
        isDialogOpen: true,
        modelValue: true,
        project,
      });
      if (existing) {
        wrapper
          .findAllComponents(Combobox)
          .find((c) => c.vm.$attrs["aria-label"] === "Location 1 target")
          .vm.$emit("update:modelValue", "LOCATION-1");
        await settle();
      }
      await new DOMWrapper(
        document.querySelector('[aria-label="Add Work Summary to Location 1"]'),
      ).trigger("click");
      const count = existing ? 2 : 4;
      expect(button(`Add ${count} Generic Tasks`).element.disabled).toBe(true);
      await fieldValue("Location 1 Work Summary 1", "Inspection");
      await fieldValue("Location 1 Work Summary 2", "Repair");
      await button(`Add ${count} Generic Tasks`).trigger("click");
      await settle();
      expect(saved[0].locations).toEqual([
        {
          subject: "General",
          ...(existing ? { task: "LOCATION-1" } : {}),
          work_summaries: ["Inspection", "Repair"],
        },
      ]);
    },
  );
});
