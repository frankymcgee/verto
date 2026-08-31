import * as React from "react";
import { Excalidraw } from "@excalidraw/excalidraw";

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
  const [theme, setTheme] = React.useState(getFrappeTheme);
  const saveTimer = React.useRef(null);
  const latestState = React.useRef(null);
  const hasLoaded = React.useRef(false);

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

        if (active) {
          hasLoaded.current = true;
        }
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
    if (!latestState.current) {
      return;
    }

    try {
      await saveState(latestState.current);
    } catch (error) {
      console.error(
        "[Verto Whiteboard] Could not save whiteboard state:",
        error
      );
    }
  }, []);

  const handleChange = React.useCallback(
    (elements, appState, files) => {
      if (!hasLoaded.current) {
        return;
      }

      latestState.current = prepareStateForSave(
        elements,
        appState,
        files
      );

      window.clearTimeout(saveTimer.current);

      saveTimer.current = window.setTimeout(() => {
        persistLatestState();
      }, SAVE_DELAY);
    },
    [persistLatestState]
  );

  React.useEffect(() => {
    const handlePageExit = () => {
      if (latestState.current) {
        saveState(latestState.current).catch(() => {
          // The browser may cancel requests while navigating away.
        });
      }
    };

    window.addEventListener("pagehide", handlePageExit);

    return () => {
      window.removeEventListener("pagehide", handlePageExit);
      window.clearTimeout(saveTimer.current);

      if (latestState.current) {
        persistLatestState();
      }
    };
  }, [persistLatestState]);

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