import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises, DOMWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { createRouter, createMemoryHistory } from "vue-router";
import { setConfig } from "frappe-ui";
import ProjectSpanDialog from "../src/components/ProjectSpanDialog.vue";
import { raiseToast } from "../src/utils";

vi.mock("../src/utils", () => ({ raiseToast: vi.fn() }));

const users = [
  { user: "alex@example.com", full_name: "Alex" },
  { user: "blake@example.com", full_name: "Blake" },
  { user: "casey@example.com", full_name: "Casey" },
  { user: "disabled@example.com", full_name: "Disabled user" },
];
let wrapper, current, saved, saveError, pickerError, releaseSave;
const getDetails = () => ({
  project: "PROJ-1",
  project_name: "Test project",
  task_count: 3,
  has_tasks: true,
  execution_tasks: [
    {
      name: "TASK-1",
      subject: "Execution Works",
      location_subject: "General",
      can_assign: true,
      assignees: users.filter((user) => current.includes(user.user)),
    },
  ],
});
const buttons = () => [...document.querySelectorAll("button")];
const button = (text) =>
  new DOMWrapper(buttons().find((el) => el.textContent.trim() === text));
const modal = () =>
  [...document.querySelectorAll("[role=dialog]")].find((el) =>
    el.querySelector("header")?.textContent.includes("Manage personnel"),
  ) || null;
const checkbox = (user) =>
  new DOMWrapper(
    [...modal().querySelectorAll('input[type="checkbox"]')].find(
      (el) => el.value === user,
    ),
  );
const settle = async () => {
  await flushPromises();
  await nextTick();
};
async function openPicker() {
  await button("Manage").trigger("click");
  await settle();
}

beforeEach(async () => {
  current = ["alex@example.com", "blake@example.com", "disabled@example.com"];
  saved = [];
  saveError = false;
  pickerError = false;
  releaseSave = null;
  vi.clearAllMocks();
  setConfig("resourceFetcher", async ({ url, params }) => {
    if (url.endsWith("get_project_planner_details")) return getDetails();
    if (url.endsWith("get_task_assignment_users")) {
      if (pickerError) throw new Error("Simulated picker failure");
      return { task: "TASK-1", users, assigned_users: [...current] };
    }
    if (url.endsWith("update_project_execution_task_assignments")) {
      saved.push(params);
      if (releaseSave)
        await new Promise((resolve) => {
          releaseSave = resolve;
        });
      if (saveError) throw new Error("Simulated save failure");
      current = [
        ...new Set([
          ...current.filter((user) => !params.remove_users.includes(user)),
          ...params.add_users,
        ]),
      ];
      return {
        task: "TASK-1",
        assigned_users: params.add_users,
        removed_users: params.remove_users,
        project_details: getDetails(),
      };
    }
    throw new Error(`Unexpected request ${url}`);
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: { template: "<div />" } }],
  });
  await router.push("/");
  await router.isReady();
  wrapper = mount(ProjectSpanDialog, {
    attachTo: document.body,
    global: { plugins: [router] },
    props: {
      isDialogOpen: true,
      modelValue: true,
      project: { project: "PROJ-1" },
    },
  });
  await settle();
});
afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = "";
});

describe("Planner task assignment editor", () => {
  it("preselects current personnel and lets disabled assignees be removed", async () => {
    await openPicker();
    expect(checkbox("alex@example.com").element.checked).toBe(true);
    expect(checkbox("disabled@example.com").element.checked).toBe(true);
    expect(checkbox("disabled@example.com").element.disabled).toBe(false);
    expect(checkbox("casey@example.com").element.checked).toBe(false);
    expect(button("Save changes").element.disabled).toBe(true);
  });

  it("replaces a person using only the selected additions and removals", async () => {
    await openPicker();
    await checkbox("alex@example.com").setValue(false);
    await checkbox("casey@example.com").setValue(true);
    expect(modal().textContent).toContain("1 to add · 1 to remove");
    await button("Save changes").trigger("click");
    await settle();
    expect(saved).toEqual([
      {
        project: "PROJ-1",
        task: "TASK-1",
        add_users: ["casey@example.com"],
        remove_users: ["alex@example.com"],
      },
    ]);
    expect(current).toEqual([
      "blake@example.com",
      "disabled@example.com",
      "casey@example.com",
    ]);
    expect(modal()).toBeNull();
    expect(document.body.textContent).toContain("Casey");
    expect(raiseToast).toHaveBeenCalledWith(
      "success",
      "Task personnel updated: 1 added, 1 removed.",
    );
  });

  it("can clear all assignments and save an empty selection", async () => {
    await openPicker();
    await button("Clear selection").trigger("click");
    expect(button("Save changes").element.disabled).toBe(false);
    await button("Save changes").trigger("click");
    await settle();
    expect(current).toEqual([]);
    expect(saved[0].add_users).toEqual([]);
    expect(saved[0].remove_users).toHaveLength(3);
    expect(document.body.textContent).toContain("Unassigned");
    expect(button("+ Assign").exists()).toBe(true);
  });

  it("cancel leaves assignments unchanged and reopening resets pending edits", async () => {
    await openPicker();
    await checkbox("alex@example.com").setValue(false);
    const cancel = new DOMWrapper(
      [...modal().querySelectorAll("button")].find(
        (el) => el.textContent.trim() === "Cancel",
      ),
    );
    await cancel.trigger("click");
    await settle();
    expect(saved).toEqual([]);
    await openPicker();
    expect(checkbox("alex@example.com").element.checked).toBe(true);
    expect(button("Save changes").element.disabled).toBe(true);
  });

  it("preserves pending selections on failure and supports retry", async () => {
    await openPicker();
    await checkbox("alex@example.com").setValue(false);
    saveError = true;
    await button("Save changes").trigger("click");
    await settle();
    expect(modal()).not.toBeNull();
    expect(checkbox("alex@example.com").element.checked).toBe(false);
    expect(current).toContain("alex@example.com");
    expect(button("Save changes").element.disabled).toBe(false);
    saveError = false;
    await button("Save changes").trigger("click");
    await settle();
    expect(current).not.toContain("alex@example.com");
  });

  it("reports picker errors without changing assignments", async () => {
    pickerError = true;
    await openPicker();
    expect(modal()).toBeNull();
    expect(saved).toEqual([]);
    expect(raiseToast).toHaveBeenCalledWith(
      "error",
      "Simulated picker failure",
    );
  });

  it("blocks further edits and closing while a save is in flight", async () => {
    await openPicker();
    await checkbox("alex@example.com").setValue(false);
    releaseSave = true;
    await button("Save changes").trigger("click");
    await settle();
    expect(checkbox("blake@example.com").element.disabled).toBe(true);
    expect(modal().querySelector('[aria-label="Close"]')).toBeNull();
    expect(modal()).not.toBeNull();
    releaseSave();
    await settle();
    expect(modal()).toBeNull();
  });

  it("loads fresh assignees when reopening a task", async () => {
    current = ["blake@example.com"];
    await openPicker();
    expect(checkbox("alex@example.com").element.checked).toBe(false);
    expect(checkbox("blake@example.com").element.checked).toBe(true);
    expect(button("Save changes").element.disabled).toBe(true);
  });

  it("does not lose selected users while filtering the picker", async () => {
    await openPicker();
    const search = new DOMWrapper(
      modal().querySelector('input[type="search"]'),
    );
    await search.setValue("Casey");
    await checkbox("casey@example.com").setValue(true);
    await button("Save changes").trigger("click");
    await settle();
    expect(saved[0].remove_users).toEqual([]);
    expect(saved[0].add_users).toEqual(["casey@example.com"]);
  });
});
