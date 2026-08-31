frappe.pages["whiteboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Whiteboard"),
    single_column: true,
  });

  wrapper.whiteboard_page = page;
};

frappe.pages["whiteboard"].on_page_show = function (wrapper) {
  load_whiteboard(wrapper);
};

frappe.pages["whiteboard"].on_page_hide = function (wrapper) {
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
  if (wrapper.whiteboard_instance) {
    wrapper.whiteboard_instance.destroy();
    wrapper.whiteboard_instance = null;
  }

  const parent = wrapper;
  $(parent).empty();

  try {
    await load_stylesheet(
      "/assets/verto/css/excalidraw.css",
      "verto-excalidraw-css"
    );

    await frappe.require([
      "whiteboard.bundle.css",
      "whiteboard.bundle.jsx",
    ]);

    wrapper.whiteboard_instance = new frappe.ui.Whiteboard({
      wrapper: parent,
      page: wrapper.whiteboard_page,
    });
  } catch (error) {
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