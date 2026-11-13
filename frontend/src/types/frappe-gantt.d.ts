declare module 'frappe-gantt' {
  export type GanttTask = {
    id: string
    name: string
    start: Date
    end: Date
    progress: number
    dependencies: string[]
    custom_class: string
    color?: string
    color_progress?: string
  }

  export type GanttOptions = {
    view_mode: 'Day' | 'Week' | 'Month'
    upper_header_height: number
    lower_header_height: number
    bar_height: number
    padding: number
    readonly: boolean
    move_dependencies: boolean
    today_button: boolean
    infinite_padding: boolean
    scroll_to: 'start'
    popup: false
  }

  export default class Gantt {
    constructor(wrapper: HTMLElement, tasks: GanttTask[], options: GanttOptions)
    refresh(tasks: GanttTask[]): void
    change_view_mode(mode: GanttOptions['view_mode']): void
    // v1.2.2 binds drag handlers to the document without a destroy method.
    bind_bar_events(): void
  }
}
