import * as React from "react";
import { createSaveQueue, sceneKey } from "./saveQueue";
import { createPage, createWorkbook, duplicatePage, movePage, normalizeWorkbook, prepareScene, workbookKey } from "./pages";
import { callWhiteboard, downloadWorkbook } from "./client";
import { PageCanvas, PageDisplay, pageFrame } from "./PageCanvas";

const SAVE_DELAY = 1500;
const POLL_DELAY = 10000;
const themeName = () => document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";

function Dialog({ title, children, onClose, onSubmit, submitLabel = "Save", busy }) {
  const ref = React.useRef(null);
  React.useEffect(() => { ref.current.showModal(); }, []);
  return <dialog ref={ref} className="verto-whiteboard-dialog" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={onSubmit}>
      <h3>{title}</h3>{children}
      <div className="verto-whiteboard-dialog-actions">
        <button type="button" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="submit" className="primary" disabled={busy}>{busy ? "Saving…" : submitLabel}</button>
      </div>
    </form>
  </dialog>;
}

export function App({ display = false, boardName = "personal", token = "", pageId = "" }) {
  const [selectedBoard, setSelectedBoard] = React.useState(boardName);
  const [boards, setBoards] = React.useState([]);
  const [board, setBoard] = React.useState(null);
  const [workbook, setWorkbook] = React.useState(null);
  const [preview, setPreview] = React.useState(display);
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState("");
  const [saveError, setSaveError] = React.useState("");
  const [status, setStatus] = React.useState("Saved");
  const [syncWarning, setSyncWarning] = React.useState("");
  const [lastChecked, setLastChecked] = React.useState(null);
  const [theme, setTheme] = React.useState(themeName);
  const [dialog, setDialog] = React.useState(null);
  const [formError, setFormError] = React.useState("");
  const workbookRef = React.useRef(null);
  const sessionRef = React.useRef(null);
  const timer = React.useRef(null);
  const dirty = React.useRef(false);
  const editorApi = React.useRef(null);
  const alive = React.useRef(true);
  const root = React.useRef(null);
  const contentKeys = React.useRef(new Map());
  const readOnly = display || preview || !board?.can_edit;
  const activePage = workbook?.pages.find(page => page.id === workbook.activePageId);

  const install = React.useCallback((snapshot, keepPage) => {
    const next = normalizeWorkbook(snapshot.state);
    const preferred = keepPage || pageId;
    if (preferred && next.pages.some(page => page.id === preferred)) next.activePageId = preferred;
    const session = { name: snapshot.name, revision: snapshot.revision, editable: snapshot.can_edit && !display };
    session.queue = createSaveQueue(async state => {
      const result = await callWhiteboard("save_whiteboard", { name: session.name, revision: session.revision, state: JSON.stringify(state) }, true);
      session.revision = result.revision;
      if (alive.current && sessionRef.current === session) setBoard(current => ({ ...current, revision: result.revision }));
    }, error => {
      if (alive.current && sessionRef.current === session) {
        setSaveError(error.message);
        setStatus("Not saved");
      }
    });
    session.queue.baseline(workbookKey(next));
    sessionRef.current = session;
    workbookRef.current = next;
    contentKeys.current.clear();
    dirty.current = false;
    setWorkbook(next);
    setBoard(snapshot);
    setSaveError("");
    setStatus("Saved");
    setLastChecked(new Date());
  }, [display, pageId]);

  const flush = React.useCallback(async () => {
    clearTimeout(timer.current);
    const session = sessionRef.current;
    if (!session?.editable || !workbookRef.current) return true;
    const snapshot = structuredClone(workbookRef.current);
    session.queue.update(workbookKey(snapshot), snapshot);
    if (session.queue.isDirty() && alive.current) setStatus("Saving…");
    const success = await session.queue.flush();
    if (success && sessionRef.current === session) {
      dirty.current = session.queue.isDirty() || workbookKey(workbookRef.current) !== workbookKey(snapshot);
      if (alive.current) {
        setSaveError("");
        setStatus(dirty.current ? "Unsaved changes" : "Saved");
        if (dirty.current) {
          clearTimeout(timer.current);
          timer.current = setTimeout(() => { void flush(); }, SAVE_DELAY);
        }
      }
    }
    return success;
  }, []);

  const load = React.useCallback(async name => {
    setLoading(true);
    setLoadError("");
    try {
      const snapshot = await callWhiteboard("get_whiteboard", { name, token });
      if (!alive.current) return;
      install(snapshot);
    } catch (error) {
      if (alive.current) {
        sessionRef.current = null;
        workbookRef.current = null;
        setWorkbook(null);
        setLoadError(error.message);
      }
    } finally { if (alive.current) setLoading(false); }
  }, [install, token]);

  React.useEffect(() => {
    alive.current = true;
    void load(boardName);
    if (!display) callWhiteboard("get_whiteboards").then(rows => { if (alive.current) setBoards(rows); }).catch(error => { if (alive.current) setSyncWarning(error.message); });
    const observer = new MutationObserver(() => setTheme(themeName()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const exiting = () => { void flush(); };
    const beforeUnload = event => {
      if (dirty.current || sessionRef.current?.queue.isDirty()) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("pagehide", exiting);
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("online", exiting);
    return () => {
      alive.current = false;
      observer.disconnect();
      window.removeEventListener("pagehide", exiting);
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("online", exiting);
      void flush();
    };
  }, []);

  React.useEffect(() => {
    if (!board || !readOnly) return;
    let active = true;
    let timeout;
    const poll = async () => {
      const session = sessionRef.current;
      if (!session) return;
      try {
        const snapshot = await callWhiteboard("get_whiteboard", { name: session.name, token, revision: session.revision });
        if (!active || sessionRef.current !== session) return;
        if (!snapshot.not_modified) install(snapshot, workbookRef.current?.activePageId);
        setLastChecked(new Date());
        setSyncWarning("");
      } catch (error) {
        if (!active) return;
        if ([403, 404].includes(error.status)) {
          setWorkbook(null);
          workbookRef.current = null;
          sessionRef.current = null;
          setLoadError(error.message);
          return;
        }
        setSyncWarning("Connection interrupted. Showing the last received board; retrying automatically.");
      } finally { if (active) timeout = setTimeout(poll, POLL_DELAY); }
    };
    timeout = setTimeout(poll, POLL_DELAY);
    return () => { active = false; clearTimeout(timeout); };
  }, [board?.name, readOnly, install, token]);

  const changed = (page, elements, appState, files) => {
    if (!sessionRef.current?.editable || readOnly) return;
    const current = workbookRef.current;
    if (current?.activePageId !== page.id) return;
    const scene = prepareScene(elements, appState, files);
    workbookRef.current = { ...current, pages: current.pages.map(item => item.id === page.id ? { ...item, scene } : item) };
    const key = sceneKey(elements, appState, files);
    const previous = contentKeys.current.get(page.id);
    contentKeys.current.set(page.id, key);
    // The first onChange is Excalidraw restoring this page, not a user edit.
    if (previous === undefined || previous === key) return;
    dirty.current = true;
    setStatus("Unsaved changes");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, SAVE_DELAY);
  };

  const commitPages = async next => {
    workbookRef.current = next;
    setWorkbook(next);
    dirty.current = true;
    await flush();
  };

  const selectPage = async id => {
    if (busy || id === workbookRef.current.activePageId) return;
    setBusy(true);
    try {
      if (!readOnly && !await flush()) return;
      const next = { ...workbookRef.current, activePageId: id };
      editorApi.current = null;
      contentKeys.current.delete(id);
      if (readOnly) { workbookRef.current = next; setWorkbook(next); }
      else await commitPages(next);
    } finally { setBusy(false); }
  };

  const selectBoard = async name => {
    setBusy(true);
    try {
      if (!await flush()) return;
      setSelectedBoard(name);
      setPreview(false);
      editorApi.current = null;
      await load(name);
    } finally { setBusy(false); }
  };

  const showDialog = (type, value = "") => { setFormError(""); setDialog({ type, value, visibility: board?.visibility || "Workspace" }); };
  const pageAction = async action => {
    if (!action || busy) return;
    const page = workbookRef.current.pages.find(item => item.id === workbookRef.current.activePageId);
    if (action === "rename") return showDialog("rename", page.title);
    if (action === "delete") return showDialog("delete");
    setBusy(true);
    try {
      if (!await flush()) return;
      const current = workbookRef.current;
      if (action === "duplicate") {
        const copy = duplicatePage(page);
        await commitPages({ ...current, activePageId: copy.id, pages: [...current.pages, copy] });
      } else await commitPages(movePage(current, page.id, action === "left" ? -1 : 1));
    } finally { setBusy(false); }
  };

  const submitDialog = async event => {
    event.preventDefault();
    setFormError("");
    setBusy(true);
    try {
      if (!await flush()) { setFormError("Save the current changes before continuing."); return; }
      const current = workbookRef.current;
      if (dialog.type === "new-board") {
        const snapshot = await callWhiteboard("create_whiteboard", { title: dialog.value.trim(), state: JSON.stringify(createWorkbook()) }, true);
        setBoards(previous => [...previous, snapshot]);
        setSelectedBoard(snapshot.name);
        setPreview(false);
        install(snapshot);
      } else if (dialog.type === "sharing") {
        const snapshot = await callWhiteboard("update_whiteboard_sharing", {
          name: board.name, revision: sessionRef.current.revision, visibility: dialog.visibility, title: dialog.value.trim(),
        }, true);
        install(snapshot, current.activePageId);
        setBoards(previous => previous.map(item => item.name === snapshot.name ? snapshot : item));
      } else if (dialog.type === "add") {
        const page = createPage(dialog.value.trim());
        await commitPages({ ...current, activePageId: page.id, pages: [...current.pages, page] });
      } else if (dialog.type === "rename") {
        await commitPages({ ...current, pages: current.pages.map(page => page.id === current.activePageId ? { ...page, title: dialog.value.trim() } : page) });
      } else if (dialog.type === "delete" && current.pages.length > 1) {
        const index = current.pages.findIndex(page => page.id === current.activePageId);
        const pages = current.pages.filter(page => page.id !== current.activePageId);
        await commitPages({ ...current, pages, activePageId: pages[Math.min(index, pages.length - 1)].id });
      }
      setDialog(null);
    } catch (error) { setFormError(error.message); }
    finally { setBusy(false); }
  };

  const displayUrl = () => {
    const url = new URL(board.display_url || `/whiteboard-display?board=${encodeURIComponent(board.name)}`, location.origin);
    url.searchParams.set("page", workbookRef.current.activePageId);
    return url.toString();
  };

  const togglePreview = async () => {
    setBusy(true);
    try {
      if (!await flush()) return;
      setWorkbook(workbookRef.current);
      contentKeys.current.clear();
      setPreview(value => !value);
    } finally { setBusy(false); }
  };

  if (loading) return <div className="verto-whiteboard-loading"><div className="verto-whiteboard-spinner" />Loading whiteboard…</div>;
  if (loadError || !workbook) return <div className="verto-whiteboard-loading" role="alert">
    <p>{loadError || "Could not load the whiteboard."}</p>
    <button onClick={() => load(selectedBoard)}>Retry</button>
    {display && <a href={`/login?redirect-to=${encodeURIComponent(location.pathname + location.search)}`}>Sign in</a>}
  </div>;

  return <div ref={root} className={`verto-whiteboard verto-whiteboard-workspace ${readOnly ? "is-viewing" : ""}`}>
    <div className="verto-whiteboard-toolbar">
      {!display ? <>
        <label className="verto-whiteboard-board-picker">Board
          <select aria-label="Whiteboard" value={selectedBoard} disabled={busy} onChange={event => selectBoard(event.target.value)}>
            <option value="personal">My whiteboard · private</option>
            {boards.map(item => <option key={item.name} value={item.name}>{item.title}</option>)}
          </select>
        </label>
        <button onClick={() => showDialog("new-board")} disabled={busy}>New shared board</button>
      </> : <strong>{board.title}</strong>}
      <span className="verto-whiteboard-status" role="status">{readOnly ? `Read-only · ${lastChecked ? `checked ${lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "connecting"}` : status}</span>
      {!display && board.can_edit && <button onClick={togglePreview} disabled={busy}>{preview ? "Edit board" : "Preview display"}</button>}
      {!display && board.can_edit && board.name !== "personal" && <button onClick={() => showDialog("sharing", board.title)} disabled={busy}>Sharing</button>}
      {readOnly && <>
        {!display && <a className="verto-whiteboard-button" href={displayUrl()} target="_blank" rel="noopener noreferrer">Open display</a>}
        <button onClick={() => {
          const action = document.fullscreenElement ? document.exitFullscreen() : (display ? document.documentElement : root.current).requestFullscreen();
          action?.catch(() => setSyncWarning("Use your browser's fullscreen option to fill the display."));
        }}>Fullscreen</button>
      </>}
    </div>
    {saveError && <div className="verto-whiteboard-alert" role="alert">
      <span>{saveError}</span><button onClick={flush}>Retry save</button>
      <button onClick={() => downloadWorkbook(workbookRef.current, board.title)}>Download unsaved copy</button>
    </div>}
    {syncWarning && <div className="verto-whiteboard-alert" role="status">{syncWarning}</div>}
    <div className="verto-whiteboard-pages">
      <div className="verto-whiteboard-tabs" role="tablist" aria-label="Whiteboard pages">
        {workbook.pages.map((page, index) => <button key={page.id} role="tab" aria-selected={page.id === workbook.activePageId}
          aria-controls="whiteboard-page-panel" disabled={busy} onClick={() => selectPage(page.id)}>{index + 1}. {page.title}</button>)}
      </div>
      {!readOnly && <div className="verto-whiteboard-page-actions">
        <button disabled={busy || workbook.pages.length >= 100} onClick={() => showDialog("add", `Page ${workbook.pages.length + 1}`)}>+ Add page</button>
        <select aria-label="Page actions" value="" disabled={busy} onChange={event => pageAction(event.target.value)}>
          <option value="">Page actions</option><option value="rename">Rename</option>
          <option value="duplicate" disabled={workbook.pages.length >= 100}>Duplicate</option>
          <option value="left" disabled={workbook.pages[0].id === activePage.id}>Move left</option>
          <option value="right" disabled={workbook.pages.at(-1).id === activePage.id}>Move right</option>
          <option value="delete" disabled={workbook.pages.length === 1}>Delete</option>
        </select>
        <button onClick={() => editorApi.current?.scrollToContent(pageFrame(activePage), { fitToViewport: true, viewportZoomFactor: 0.85, animate: true })}>Fit page</button>
      </div>}
    </div>
    {!readOnly && <div className="verto-whiteboard-hint">Draw inside the page frame. The display shows only this page.</div>}
    <div id="whiteboard-page-panel" role="tabpanel" aria-label={activePage.title} className="verto-whiteboard-page-content" inert={busy ? true : undefined}>
      {readOnly ? <PageDisplay page={activePage} revision={board.revision} /> : <PageCanvas key={`${board.name}:${activePage.id}`}
        page={activePage} theme={theme} onApi={api => { editorApi.current = api; }} onChange={(...args) => changed(activePage, ...args)} />}
    </div>
    {dialog && <Dialog busy={busy} title={{ add: "Add page", rename: "Rename page", delete: "Delete page", "new-board": "New shared board", sharing: "Board sharing" }[dialog.type]}
      onClose={() => setDialog(null)} onSubmit={submitDialog} submitLabel={dialog.type === "delete" ? "Delete page" : "Save"}>
      {dialog.type !== "delete" ? <label>Name<input autoFocus required maxLength={140} value={dialog.value}
        onChange={event => setDialog({ ...dialog, value: event.target.value })} /></label> : <p>Delete “{activePage.title}” and its drawing? Other pages will be kept.</p>}
      {dialog.type === "new-board" && <p>Signed-in Desk users can view this board. You and System Managers can edit it.</p>}
      {dialog.type === "sharing" && <>
        <label>Who can view this board?<select aria-label="Who can view this board?" value={dialog.visibility} onChange={event => setDialog({ ...dialog, visibility: event.target.value })}>
          <option value="Private">Only me and System Managers</option>
          <option value="Workspace">Signed-in Desk users</option>
          <option value="Public link">Anyone with the display link</option>
        </select></label>
        <p>Only you and System Managers can edit. Public links allow viewing every page without signing in. Switching away from public access revokes the old link.</p>
        {board.display_url && <label>Current display link<input readOnly value={displayUrl()} onFocus={event => event.target.select()} /></label>}
      </>}
      {formError && <p role="alert">{formError}</p>}
    </Dialog>}
  </div>;
}
