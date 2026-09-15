// Only content changes trigger an upload. Excalidraw increments an element's
// version on edits, undo and redo; selecting, hovering, panning and zooming do not.
export function sceneKey(elements, appState, files) {
  return JSON.stringify({
    elements: elements.map(({ id, version, versionNonce, isDeleted }) => [id, version, versionNonce, isDeleted]),
    files: Object.keys(files || {}).sort(),
    background: appState?.viewBackgroundColor,
  });
}

export function createSaveQueue(save, onError) {
  let latest = null;
  let savedKey;
  let inFlight = null;

  return {
    baseline(key) { savedKey = key; },
    update(key, state) {
      latest = { key, state };
      return key !== savedKey;
    },
    flush() {
      if (inFlight) return inFlight;
      inFlight = (async () => {
        while (latest && latest.key !== savedKey) {
          const snapshot = latest;
          try {
            await save(snapshot.state);
            savedKey = snapshot.key;
          } catch (error) {
            onError(error);
            break; // Keep the dirty snapshot for a later retry; never spin.
          }
        }
      })().finally(() => { inFlight = null; });
      return inFlight;
    },
  };
}
