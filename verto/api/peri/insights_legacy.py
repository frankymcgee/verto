"""Adapter for the Insights 3.14 dashboard and chart query APIs."""

import re

import frappe

DASHBOARD = "Insights Dashboard v3"
CHART = "Insights Chart v3"
QUERY = "Insights Query v3"
FILTER_LINK = re.compile(r"`([^`]+)`\.`([^`]+)`")
COUNT = {
    "column_name": "count",
    "data_type": "Integer",
    "aggregation": "count",
    "measure_name": "count_of_rows",
}


def get_dashboards():
    from insights.decorators import has_role

    if not has_role("Insights User"):
        frappe.throw("Insights access is required.", frappe.PermissionError)
    return frappe.get_list(DASHBOARD, fields=["name", "title"], limit_page_length=0)


def get_dashboard(dashboard):
    doc = frappe.get_doc(DASHBOARD, dashboard)
    doc.check_permission("read")
    items = frappe.parse_json(doc.items) or []
    charts = {}
    for item in items:
        name = item.get("chart")
        if item.get("type") != "chart" or not name or name in charts:
            continue
        if frappe.db.exists(CHART, name) and frappe.has_permission(CHART, "read", doc=name):
            chart = frappe.get_doc(CHART, name)
            charts[name] = {
                "name": name,
                "title": chart.title,
                "chart_type": chart.chart_type,
                "config": frappe.parse_json(chart.config) or {},
            }

    return {
        "name": doc.name,
        "title": doc.title,
        "items": [
            {**item, "charts": [
                name for name, link in (item.get("links") or {}).items()
                if name in charts and link and FILTER_LINK.fullmatch(link)
            ]} if item.get("type") == "filter" else item
            for item in items
        ],
        "charts": list(charts.values()),
    }


def get_chart_data(chart, dashboard, filters):
    doc = frappe.get_doc(DASHBOARD, dashboard)
    doc.check_permission("read")
    items = frappe.parse_json(doc.items) or []
    if not any(item.get("type") == "chart" and item.get("chart") == chart for item in items):
        raise frappe.PermissionError

    chart = frappe.get_doc(CHART, chart)
    chart.check_permission("read")
    source = frappe.get_doc(QUERY, chart.query)
    source.check_permission("read")
    query = frappe.get_doc(QUERY, chart.data_query)
    query.check_permission("read")

    config = frappe.parse_json(chart.config) or {}
    operations = [
        {"type": "source", "table": {"type": "query", "workbook": "", "query_name": source.name}},
    ]
    if (chart_filters := config.get("filters")) and chart_filters.get("filters"):
        operations.append({"type": "filter_group", **chart_filters})
    operations.extend(chart_operations(chart.chart_type, config))
    for sort in config.get("order_by") or []:
        if (name := sort["column"].get("column_name")) and sort.get("direction"):
            add_sort(operations, name, sort["direction"])

    # Insights 3.14 builds these operations in the browser and sends them to
    # the saved data query for execution. Keep the replacement in memory.
    query.operations = frappe.as_json(operations)
    query.use_live_connection = source.use_live_connection
    return query.execute(
        active_operation_idx=len(operations) - 1,
        adhoc_filters=route_filters(items, chart.name, filters),
        page_size=int(config.get("limit") or 100),
    )


def chart_operations(chart_type, config):
    pivot_columns = []
    pivot_limit = 10
    if chart_type in {"Bar", "Line", "Row"}:
        axis = config.get("x_axis") or {}
        dimensions = [axis.get("dimension") or axis]
        y_axis = config.get("y_axis") or {}
        measures = y_axis if isinstance(y_axis, list) else [
            series.get("measure") for series in y_axis.get("series", [])
        ]
        measures = [measure for measure in measures if measure and measure.get("measure_name")] or [COUNT]
        split = config.get("split_by") or {}
        if (split.get("dimension") or {}).get("column_name"):
            pivot_columns = [split["dimension"]]
            pivot_limit = split.get("max_split_values") or 10
    elif chart_type == "Number":
        dimensions = [config.get("date_column")]
        measures = config.get("number_columns") or []
    elif chart_type in {"Donut", "Funnel", "Map"}:
        dimensions = [config.get("location_column" if chart_type == "Map" else "label_column")]
        measures = [config.get("value_column")]
    elif chart_type == "Table":
        dimensions = config.get("rows") or []
        measures = config.get("values") or []
        pivot_columns = [col for col in config.get("columns") or [] if col.get("column_name")]
        pivot_limit = config.get("max_column_values") or 10
    elif chart_type == "Bubble":
        dimensions = [config.get(key) for key in ("dimension", "quadrant_column")]
        measures = [config.get(key) for key in ("xAxis", "yAxis", "size_column")]
    elif chart_type == "Safety Cross":
        dimensions = [config.get(key) for key in ("date_column", "shift_column", "status_column", "detail_column")]
        measures = [COUNT]
    elif chart_type == "Sankey":
        # The v3.14 chart consumes the source rows directly.
        return []
    else:
        raise ValueError(f"Unsupported Insights 3.14 chart type: {chart_type}")

    dimensions = [dimension for dimension in dimensions if dimension and dimension.get("column_name")]
    measures = [measure for measure in measures if measure and measure.get("measure_name")]
    if pivot_columns:
        return [{
            "type": "pivot_wider", "rows": dimensions, "columns": pivot_columns,
            "values": measures, "max_column_values": pivot_limit,
        }]
    if not dimensions and not measures:
        raise ValueError("The saved chart has no dimensions or measures")
    operations = [{"type": "summarize", "dimensions": dimensions, "measures": measures}]
    if chart_type in {"Donut", "Funnel"} and measures:
        add_sort(operations, measures[0]["measure_name"], "desc")
    return operations


def add_sort(operations, name, direction):
    sort = {"type": "order_by", "column": column(name), "direction": direction}
    for index, operation in enumerate(operations):
        if operation["type"] == "order_by" and operation["column"]["column_name"] == name:
            operations[index] = sort
            return
    operations.append(sort)


def column(name):
    return {"type": "column", "column_name": name}


def route_filters(items, chart, filters):
    groups = {}
    for item in items:
        if item.get("type") != "filter":
            continue
        state = filters.get(item.get("filter_name"))
        link = (item.get("links") or {}).get(chart)
        match = FILTER_LINK.fullmatch(link) if link else None
        if not state or not match:
            continue
        query, name = match.groups()
        operator = state["operator"]
        value = state.get("value")
        if value in (None, "", []) and operator not in {"is_set", "is_not_set"}:
            continue
        group = groups.setdefault(query, {"type": "filter_group", "logical_operator": "And", "filters": []})
        group["filters"].append({"type": "filter", "column": column(name), "operator": operator, "value": value})
    return groups or None
