import { sceneKey } from "./saveQueue.js";

export const PAGE_WIDTH = 1600;
export const PAGE_HEIGHT = 900;

export function createPage(title = "Page 1") {
  return {
    id: crypto.randomUUID(), title,
    bounds: { x: 0, y: 0, width: PAGE_WIDTH, height: PAGE_HEIGHT },
    scene: { type: "excalidraw", version: 2, source: "verto", elements: [], appState: { viewBackgroundColor: "#ffffff" }, files: {} },
  };
}

export function createWorkbook() {
  const page = createPage();
  return { type: "verto-whiteboard", version: 1, activePageId: page.id, pages: [page] };
}

function legacyBounds(elements) {
  const visible = elements.filter((element) => !element.isDeleted);
  if (!visible.length) return { x: 0, y: 0, width: PAGE_WIDTH, height: PAGE_HEIGHT };
  const edges = visible.map(({ x = 0, y = 0, width = 0, height = 0, angle = 0 }) => {
    const halfWidth = (Math.abs(width * Math.cos(angle)) + Math.abs(height * Math.sin(angle))) / 2;
    const halfHeight = (Math.abs(width * Math.sin(angle)) + Math.abs(height * Math.cos(angle))) / 2;
    return [x + width / 2 - halfWidth, y + height / 2 - halfHeight, x + width / 2 + halfWidth, y + height / 2 + halfHeight];
  });
  const left = Math.min(...edges.map(e => e[0])) - 40;
  const top = Math.min(...edges.map(e => e[1])) - 40;
  return { x: left, y: top, width: Math.max(PAGE_WIDTH, Math.max(...edges.map(e => e[2])) + 40 - left), height: Math.max(PAGE_HEIGHT, Math.max(...edges.map(e => e[3])) + 40 - top) };
}

export function normalizeWorkbook(value) {
  const state = typeof value === "string" ? JSON.parse(value) : value;
  if (!state || (typeof state === "object" && Object.keys(state).length === 0)) return createWorkbook();
  if (state.type === "verto-whiteboard" && state.version === 1 && state.pages?.length) {
    if (!state.pages.some(page => page.id === state.activePageId)) throw new Error("Invalid selected page.");
    return state;
  }
  if (state.type === "excalidraw" && Array.isArray(state.elements)) {
    const page = createPage();
    page.scene = { ...state, appState: state.appState || {}, files: state.files || {} };
    page.bounds = legacyBounds(state.elements);
    return { type: "verto-whiteboard", version: 1, activePageId: page.id, pages: [page] };
  }
  throw new Error("This saved whiteboard format cannot be opened. Your existing data has not been changed.");
}

export function prepareScene(elements, appState, files) {
  const { collaborators, openDialog, openMenu, contextMenu, toast, selectedElementIds,
    selectedGroupIds, editingGroupId, width, height, offsetTop, offsetLeft,
    ...savedState } = appState || {};
  return { type: "excalidraw", version: 2, source: "verto", elements, appState: savedState, files: files || {} };
}

export function workbookKey(workbook) {
  return JSON.stringify({ activePageId: workbook.activePageId, pages: workbook.pages.map(page => ({
    id: page.id, title: page.title, bounds: page.bounds,
    content: sceneKey(page.scene.elements, page.scene.appState, page.scene.files),
    scrollX: page.scene.appState.scrollX, scrollY: page.scene.appState.scrollY,
    zoom: page.scene.appState.zoom,
  })) });
}

export function duplicatePage(page) {
  return { ...structuredClone(page), id: crypto.randomUUID(), title: `${page.title.slice(0, 130)} (copy)` };
}

export function movePage(workbook, pageId, direction) {
  const pages = [...workbook.pages];
  const index = pages.findIndex(page => page.id === pageId);
  const next = index + direction;
  if (index < 0 || next < 0 || next >= pages.length) return workbook;
  [pages[index], pages[next]] = [pages[next], pages[index]];
  return { ...workbook, pages };
}
