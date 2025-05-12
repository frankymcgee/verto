frappe.provide("frappe.views");

frappe.views.GanttView = class GanttView extends frappe.views.ListView {
	get view_name() {
		return "Gantt";
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = this.page_title + " " + __("Gantt");
			this.calendar_settings = frappe.views.calendar[this.doctype] || {};

			if (typeof this.calendar_settings.gantt == "object") {
				Object.assign(this.calendar_settings, this.calendar_settings.gantt);
			}

			if (this.calendar_settings.order_by) {
				this.sort_by = this.calendar_settings.order_by;
				this.sort_order = "asc";
			} else {
				this.sort_by =
					this.view_user_settings.sort_by || this.calendar_settings.field_map.start;
				this.sort_order = this.view_user_settings.sort_order || "asc";
			}
		});
	}

	setup_view() {}

	prepare_data(data) {
		super.prepare_data(data);
		this.prepare_tasks();
	}

	prepare_tasks() {
		var me = this;
		var meta = this.meta;
		var field_map = this.calendar_settings.field_map;
	
		this.tasks = this.data.map(function (item) {
			// Set progress
			var progress = 0;
			if (field_map.progress && $.isFunction(field_map.progress)) {
				progress = field_map.progress(item);
			} else if (field_map.progress) {
				progress = item[field_map.progress];
			}
	
			// Title
			var label;
			if (meta.title_field) {
				label = item.progress
					? __("{0} ({1}) - {2}%", [item[meta.title_field], item.name, item.progress])
					: __("{0} ({1})", [item[meta.title_field], item.name]);
			} else {
				label = item[field_map.title];
			}
	
			// Parse start and end times using the exp_start_time for HH:mm:ss
			var date_part_start = moment(item[field_map.start], 'YYYY-MM-DD');
			var time_part_start = moment(item.exp_start_time, 'HH:mm:ss');
			var date_part_end = moment(item[field_map.end], 'YYYY-MM-DD');
			var time_part_end = moment(item.exp_end_time, 'HH:mm:ss');
	
			// Combine date and time parts for start and end times
			var start_time = date_part_start
				.hour(time_part_start.hour())
				.minute(time_part_start.minute())
				.second(time_part_start.second())
				.subtract(12, 'hours');
	
			var end_time = date_part_end
				.hour(time_part_end.hour())
				.minute(time_part_end.minute())
				.second(time_part_end.second())
				.subtract(12, 'hours');
	
			// Check if start_time and end_time are valid
			if (!start_time.isValid() || !end_time.isValid()) {
				console.error("Invalid date:", item);
				return null; // Skip this item if dates are invalid
			}
	
			var r = {
				start: start_time.toDate(),  // Ensure the start and end are Date objects
				end: end_time.toDate(),
				name: label,
				id: item[field_map.id || "name"],
				doctype: me.doctype,
				progress: progress,
				dependencies: item.depends_on_tasks || "",
				task: item.subject,
			};
	
			// Check for color: use item.color, if not available, fallback to item.color_label
			let color_value = item.color || item.color_label;
			if (color_value && frappe.ui.color.validate_hex(color_value)) {
				r["custom_class"] = "color-" + color_value.substr(1);
			}
	
			if (item.is_milestone) {
				r["custom_class"] = "bar-milestone";
			}
	
			return r;
		}).filter(item => item !== null);  // Filter out any null items
	}
	

	render() {
		this.load_lib.then(() => {
			// Create a container for the task names list
        this.$result.empty();
        this.$result.addClass("gantt-modern");

        const $taskColumn = $('<div class="gantt-task-column"></div>');
        const $ganttContainer = $('<div class="gantt-chart-container"></div>');

        this.$result.append($taskColumn);   // Add task list container
        this.$result.append($ganttContainer); // Add Gantt chart container

        // Call the method that will render the task names
        this.render_task_column($taskColumn);

        // Render the Gantt chart
        this.render_gantt($ganttContainer);
    });
}
render_task_column($taskColumn) {
    const me = this;

    // Create a header for the task names column
    const $header = $('<div class="gantt-task-header"><strong>Tasks</strong></div>');
    $taskColumn.append($header);

    // Loop through the tasks and add each task name to the column
    this.tasks.forEach(task => {        
        // Determine the display name
        const displayName = task.task || task.name || "Unnamed Task";

        // Create task item
        const $taskItem = $(`<div class="gantt-task-item">${displayName}</div>`);        

        // Optional: Add a click handler to focus on the task in the Gantt chart
        $taskItem.on("click", () => {
            frappe.set_route("Form", task.doctype, task.id);
        });

        $taskColumn.append($taskItem);
    });
}


	render_header() {}	

	render_gantt($ganttContainer) {
    const me = this;
    const gantt_view_mode = this.view_user_settings.gantt_view_mode || "Day";
    const field_map = this.calendar_settings.field_map;
    const date_format = "YYYY-MM-DD HH:mm:ss";

    $ganttContainer.empty();

    this.gantt = new Gantt($ganttContainer[0], this.tasks, {
        bar_height: 35,
        bar_corner_radius: 4,
        view_mode: gantt_view_mode,
        date_format: date_format,
        on_click: (task) => {
            frappe.set_route("Form", task.doctype, task.id);
        },
        on_date_change: (task, start, end) => {
            if (!me.can_write) return;
            frappe.db.set_value(task.doctype, task.id, {
                [field_map.start]: moment(start).utc().format(date_format),
                [field_map.end]: moment(end).utc().format(date_format),
            });
        },
        on_progress_change: (task, progress) => {
            if (!me.can_write) return;
            var progress_fieldname = "progress";

            if ($.isFunction(field_map.progress)) {
                progress_fieldname = null;
            } else if (field_map.progress) {
                progress_fieldname = field_map.progress;
            }

            if (progress_fieldname) {
                frappe.db.set_value(task.doctype, task.id, {
                    [progress_fieldname]: parseInt(progress),
                });
            }
        },
        on_view_change: (mode) => {
            me.save_view_user_settings({
                gantt_view_mode: mode,
            });
        },
        custom_popup_html: (task) => {
            var item = me.get_item(task.id);

            var html = `<div class="title">${task.name}</div>
                <div class="subtitle">${moment(task._start).format("MMM D")} - ${moment(task._end).format(
                "MMM D"
            )}</div>`;

            var custom = me.settings.gantt_custom_popup_html;
            if (custom && $.isFunction(custom)) {
                var ganttobj = task;
                html = custom(ganttobj, item);
            }
			setTimeout(() => {
				const popup = document.querySelector(".details-container");
				if (popup) {
					popup.addEventListener("click", function () {
						const doctype = this.getAttribute("data-doctype");
						const id = this.getAttribute("data-id");
						if (doctype && id) {
							frappe.set_route("Form", doctype, id);
						}
					});
				}
			}, 10);
			
            return `
				<div class="details-container" 
					style="pointer-events:auto;cursor:pointer;padding:8px;" 
					data-doctype="${task.doctype}" 
					data-id="${task.id}">
					${html}
				</div>`;
        },		
    });	
    this.setup_view_mode_buttons();
    this.set_colors();
}


	setup_view_mode_buttons() {
		// view modes (for translation) __("Day"), __("Week"), __("Month"),
		//__("Half Day"), __("Quarter Day")

		let $btn_group = this.$paging_area.find(".gantt-view-mode");
		if ($btn_group.length > 0) return;

		const view_modes = this.gantt.options.view_modes || [];
		const active_class = (view_mode) => (this.gantt.view_is(view_mode) ? "btn-info" : "");
		const html = `<div class="btn-group gantt-view-mode">
				${view_modes
					.map(
						(value) => `<button type="button"
						class="btn btn-default btn-sm btn-view-mode ${active_class(value)}"
						data-value="${value}">
						${__(value)}
					</button>`
					)
					.join("")}
			</div>`;

		this.$paging_area.find(".level-left").append(html);

		// change view mode asynchronously
		const change_view_mode = (value) =>
			setTimeout(() => this.gantt.change_view_mode(value), 0);

		this.$paging_area.on("click", ".btn-view-mode", (e) => {
			const $btn = $(e.currentTarget);
			this.$paging_area.find(".btn-view-mode").removeClass("btn-info");
			$btn.addClass("btn-info");

			const value = $btn.data().value;
			change_view_mode(value);
		});
	}

	set_colors() {
		const classes = this.tasks
			.map((t) => t.custom_class)
			.filter((c) => c && typeof c === "string" && c.startsWith("color-"));
	
		let style = classes
			.map((c) => {
				const class_name = c.replace("#", "");
				const bar_color = "#" + c.substring(6);
				const progress_color = frappe.ui.color.get_contrast_color(bar_color);
	
				return `
					.gantt .bar-wrapper.${class_name} .bar {
						fill: ${bar_color};
					}
					.gantt .bar-wrapper.${class_name} .bar-progress {
						fill: ${progress_color};
					}
				`;
			})
			.join("");
	
		if (style) {
			style = `<style>${style}</style>`;
			this.$result.prepend(style);
		}
	}
	

	get_item(name) {
		return this.data.find((item) => item.name === name);
	}

	get required_libs() {
		return [
			"assets/frappe/node_modules/frappe-gantt/dist/frappe-gantt.css",
			"assets/frappe/node_modules/frappe-gantt/dist/frappe-gantt.min.js",
		];
	}
	
};
