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

function load_whiteboard(wrapper) {
  const parent = wrapper;

  if (wrapper.whiteboard_instance) {
    wrapper.whiteboard_instance.destroy();
    wrapper.whiteboard_instance = null;
  }

  $(parent).empty();

  frappe.require([
	"excalidraw.bundle.css",
	"whiteboard.bundle.css",
	"whiteboard.bundle.jsx",
	]).then(() => {
	wrapper.whiteboard_instance = new frappe.ui.Whiteboard({
		wrapper: parent,
		page: wrapper.whiteboard_page,
	});
	});
}