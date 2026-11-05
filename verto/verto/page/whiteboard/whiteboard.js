frappe.pages["whiteboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Whiteboard"),
    single_column: true,
  });

  $(wrapper).addClass("verto-whiteboard-page");
  wrapper.whiteboard_page = page;
  wrapper.whiteboard_mount = $('<div class="verto-whiteboard-host"></div>')
    .appendTo(page.main)
    .get(0);
};

frappe.pages["whiteboard"].on_page_show = function (wrapper) {
  load_whiteboard(wrapper);
};

frappe.pages["whiteboard"].on_page_hide = function (wrapper) {
  wrapper.whiteboard_load_token = null;
  if (wrapper.whiteboard_instance) {
    wrapper.whiteboard_instance.destroy();
    wrapper.whiteboard_instance = null;
  }
};

function load_stylesheet(href, id) {
  const existing = document.getElementById(id);

  if (existing) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const stylesheet = document.createElement("link");

    stylesheet.id = id;
    stylesheet.rel = "stylesheet";
    stylesheet.type = "text/css";
    stylesheet.href = href;

    stylesheet.onload = resolve;
    stylesheet.onerror = () => {
      stylesheet.remove();
      reject(new Error(`Could not load stylesheet: ${href}`));
    };

    document.head.appendChild(stylesheet);
  });
}

async function load_whiteboard(wrapper) {
  const loadToken = {};
  wrapper.whiteboard_load_token = loadToken;

  if (wrapper.whiteboard_instance) {
    wrapper.whiteboard_instance.destroy();
    wrapper.whiteboard_instance = null;
  }

  try {
    await load_stylesheet(
      "/assets/verto/css/excalidraw.css",
      "verto-excalidraw-css"
    );

    await frappe.require([
      "whiteboard.bundle.css",
      "whiteboard.bundle.jsx",
    ]);

    // Asset loading may finish after the user has left or reopened this page.
    if (wrapper.whiteboard_load_token !== loadToken) return;

    wrapper.whiteboard_instance = new frappe.ui.Whiteboard({
      wrapper: wrapper.whiteboard_mount,
      page: wrapper.whiteboard_page,
    });
  } catch (error) {
    if (wrapper.whiteboard_load_token !== loadToken) return;
    console.error("[Verto Whiteboard] Failed to load:", error);

    frappe.msgprint({
      title: __("Whiteboard Error"),
      message: __(
        "The whiteboard assets could not be loaded. Please refresh the page."
      ),
      indicator: "red",
    });
  }
}
