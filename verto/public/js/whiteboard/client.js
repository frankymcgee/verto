export async function callWhiteboard(method, args = {}, write = false) {
  const url = new URL(`/api/method/verto.api.whiteboard.${method}`, window.location.origin);
  const options = { method: write ? "POST" : "GET", credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } };
  if (write) {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-Frappe-CSRF-Token"] = window.frappe?.csrf_token || window.csrf_token || "";
    options.body = JSON.stringify(args);
  } else {
    Object.entries(args).forEach(([key, value]) => { if (value !== undefined && value !== null) url.searchParams.set(key, value); });
  }
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok || result.exc) {
    let message = "Could not connect to the whiteboard. Please try again.";
    try { message = JSON.parse(JSON.parse(result._server_messages)[0]).message || message; } catch { /* Generic network error. */ }
    const error = new Error(message);
    error.status = response.status;
    error.type = result.exc_type;
    throw error;
  }
  return result.message;
}

export function downloadWorkbook(workbook, title) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(workbook, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[^a-z0-9 _-]/gi, "_") || "whiteboard"}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
