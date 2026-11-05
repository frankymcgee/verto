import * as React from "react";
import { Excalidraw, convertToExcalidrawElements, exportToSvg } from "@excalidraw/excalidraw";

export function pageFrame(page) {
  const existing = page.scene.elements.find(element => element.id === `page-frame-${page.id}` && !element.isDeleted);
  if (existing) return { ...existing, ...page.bounds, name: page.title, locked: true };
  const [frame] = convertToExcalidrawElements([{
    type: "frame", children: [], id: `page-frame-${page.id}`, ...page.bounds,
    name: page.title, locked: true,
  }], { regenerateIds: false });
  return { ...frame, ...page.bounds };
}

export function PageCanvas({ page, theme, onChange, onApi }) {
  const apiRef = React.useRef(null);
  const fixedFrame = React.useMemo(() => pageFrame(page), [page.id, page.title, page.bounds]);
  const initialData = React.useMemo(() => {
    const frame = fixedFrame;
    // Page frames remain fixed; each mounted editor receives one page only.
    const elements = page.scene.elements.filter(element => !element.id?.startsWith("page-frame-"))
      .map(element => element.frameId?.startsWith("page-frame-") ? { ...element, frameId: frame.id } : element);
    return { ...page.scene, elements: [...elements, frame], appState: {
      ...page.scene.appState, frameRendering: { enabled: true, clip: true, name: true, outline: true },
    } };
  }, []);
  const receiveApi = React.useCallback(api => {
    apiRef.current = api;
    onApi(api);
    if (!page.scene.appState.zoom) {
      requestAnimationFrame(() => api.scrollToContent(pageFrame(page), { fitToViewport: true, viewportZoomFactor: 0.85, animate: false }));
    }
  }, []);
  const handleChange = (elements, appState, files) => {
    const frame = fixedFrame;
    const current = elements.find(element => element.id === frame.id && !element.isDeleted);
    if (!current || !current.locked || current.name !== page.title ||
        ["x", "y", "width", "height"].some(key => current[key] !== frame[key])) {
      apiRef.current?.updateScene({ elements: [...elements.filter(element => element.id !== frame.id), frame] });
      return;
    }
    onChange(elements, appState, files);
  };
  return <Excalidraw initialData={initialData} excalidrawAPI={receiveApi} onChange={handleChange}
    theme={theme} name={page.title} UIOptions={{ canvasActions: { loadScene: true, saveAsImage: true, export: { saveFileToDisk: true } } }} />;
}

export function PageDisplay({ page, revision }) {
  const container = React.useRef(null);
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    let active = true;
    setError("");
    container.current.replaceChildren();
    const frame = pageFrame(page);
    const elements = page.scene.elements.filter(element => !element.isDeleted && !["frame", "magicframe"].includes(element.type))
      .map(element => ({ ...element, frameId: frame.id, link: null }));
    exportToSvg({ elements: [...elements, frame], files: page.scene.files,
      appState: { ...page.scene.appState, exportBackground: true, exportPadding: 0, exportWithDarkMode: false, exportEmbedScene: false },
      exportingFrame: frame, renderEmbeddables: false,
    }).then(svg => {
      if (!active) return;
      svg.setAttribute("width", "100%");
      svg.setAttribute("height", "100%");
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      // Desk's global mobile font rule must not alter the drawing's text sizes.
      svg.querySelectorAll("[font-size]").forEach(element => {
        element.style.setProperty("font-size", element.getAttribute("font-size"), "important");
      });
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", page.title);
      container.current.replaceChildren(svg);
    }).catch(() => { if (active) setError("Could not render this page. Please reload the display."); });
    return () => { active = false; };
  }, [page, revision]);
  return <div className="verto-whiteboard-display-canvas">
    <div ref={container} className="verto-whiteboard-display-page" />
    {error && <p role="alert">{error}</p>}
  </div>;
}
