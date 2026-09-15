import * as React from "react";
import { Excalidraw } from "@excalidraw/excalidraw";
import { createSaveQueue, sceneKey } from "./saveQueue";

const SAVE_DELAY = 1500;

function getFrappeTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";
}

function prepareStateForSave(elements, appState, files) {
  const {
    collaborators,
    openDialog,
    openMenu,
    contextMenu,
    toast,
    ...savableAppState
  } = appState || {};

  return {
    type: "excalidraw",
    version: 1,
    source: "verto",
    elements,
    appState: savableAppState,
    files: files || {},
  };
}

function saveState(state) {
  return frappe.call({
    method: "verto.api.whiteboard.save_user_whiteboard_state",
    args: {
      state: JSON.stringify(state),
    },
  });
}

async function loadState() {
  const response = await frappe.db.get_value(
    "User Whiteboard State",
    frappe.session.user,
    "state"
  );

  const savedValue = response?.message?.state;

  if (!savedValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(savedValue);

    /*
     * Existing tldraw data cannot be loaded into Excalidraw.
     * Ignore it without deleting it from the database.
     */
    if (parsed?.type !== "excalidraw") {
      console.warn(
        "[Verto Whiteboard] Existing state is not an Excalidraw document."
      );
      return null;
    }

    return {
      elements: parsed.elements || [],
      appState: parsed.appState || {},
      files: parsed.files || {},
      scrollToContent: true,
    };
  } catch (error) {
    console.error(
      "[Verto Whiteboard] Could not parse saved whiteboard state:",
      error
    );

    return null;
  }
}

export function App() {
  const [initialData, setInitialData] = React.useState(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(false);
  const [theme, setTheme] = React.useState(getFrappeTheme);
  const saveTimer = React.useRef(null);
  const hasLoaded = React.useRef(false);
  const hasInitialScene = React.useRef(false);
  const saveQueue = React.useRef(null);
  if (!saveQueue.current) {
    saveQueue.current = createSaveQueue(saveState, (error) => {
      console.error("[Verto Whiteboard] Could not save whiteboard state:", error);
    });
  }

  React.useEffect(() => {
    let active = true;

    loadState()
      .then((state) => {
        if (active) {
          setInitialData(state);
          hasLoaded.current = true;
        }
      })
      .catch((error) => {
        console.error(
          "[Verto Whiteboard] Could not load whiteboard state:",
          error
        );

        // A failed load must not allow a blank canvas to overwrite saved work.
        if (active) setLoadError(true);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  React.useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(getFrappeTheme());
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => observer.disconnect();
  }, []);

  const persistLatestState = React.useCallback(async () => {
    await saveQueue.current.flush();
  }, []);

  const handleChange = React.useCallback(
    (elements, appState, files) => {
      if (!hasLoaded.current) {
        return;
      }

      const key = sceneKey(elements, appState, files);
      if (!hasInitialScene.current) {
        hasInitialScene.current = true;
        saveQueue.current.baseline(key);
      }
      const state = prepareStateForSave(
        elements,
        appState,
        files
      );

      if (!saveQueue.current.update(key, state)) return;

      window.clearTimeout(saveTimer.current);

      saveTimer.current = window.setTimeout(() => {
        persistLatestState();
      }, SAVE_DELAY);
    },
    [persistLatestState]
  );

  React.useEffect(() => {
    const handlePageExit = () => {
      window.clearTimeout(saveTimer.current);
      void persistLatestState();
    };

    window.addEventListener("pagehide", handlePageExit);

    return () => {
      window.removeEventListener("pagehide", handlePageExit);
      window.clearTimeout(saveTimer.current);

      void persistLatestState();
    };
  }, [persistLatestState]);

  if (loadError) {
    return <div className="verto-whiteboard-loading">
      <span>{__("Could not load your whiteboard. Reload the page to try again.")}</span>
    </div>;
  }

  if (isLoading) {
    return (
      <div className="verto-whiteboard-loading">
        <div className="verto-whiteboard-spinner" />
        <span>{__("Loading whiteboard…")}</span>
      </div>
    );
  }

  return (
    <div className="verto-whiteboard">
      <Excalidraw
        initialData={initialData}
        onChange={handleChange}
        theme={theme}
        name="Verto Whiteboard"
        UIOptions={{
          canvasActions: {
            loadScene: true,
            saveAsImage: true,
            export: {
              saveFileToDisk: true,
            },
          },
        }}
      />
    </div>
  );
}
