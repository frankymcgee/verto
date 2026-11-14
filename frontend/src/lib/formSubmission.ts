export function preserveWorkOrderTask(
  submitted: Record<string, unknown>,
  values: Record<string, unknown>,
) {
  // Work Order Number mode hides Work Scope. Keep the selected Task as a
  // candidate so the server can verify it against the project and work order.
  if (submitted.scope_or_wo === 'Work Order Number' && typeof values.link_task === 'string' && values.link_task) {
    submitted.link_task = values.link_task
  }
}
