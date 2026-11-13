import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Home from '../src/pages/Home.vue'
import ProjectGantt from '../src/pages/ProjectGantt.vue'
import ProjectGanttTimeline from '../src/components/ProjectGanttTimeline.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), navigate: vi.fn(), route: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.navigate }),
  useRoute: mocks.route,
}))

let wrapper
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

async function clickButton(label) {
  const button = [...document.querySelectorAll('button')].find((node) =>
    node.textContent.includes(label)
  )
  expect(button, `button containing ${label}`).toBeTruthy()
  button.click()
  await flushPromises()
}

async function openLocation(start, end, projectTools = []) {
  const errors = []
  mocks.api.mockResolvedValue({ message: {
    grouped_tasks: [{
      scope_name: 'Shutdown', project: 'PROJ-1', project_details: {},
      parent_groups: [{
        parent_task_name: 'Plant Room', parent_task: 'AREA-1', project: 'PROJ-1', progress: 25,
        tasks: [{
          name: 'TASK-1', subject: 'Inspect pump', status: 'Open',
          exp_start_date: '2026-11-05', exp_end_date: '2026-11-06',
          exp_start_time: start, exp_end_time: end,
        }],
      }],
    }],
    generic_forms: [], project_tools: projectTools,
    task_forms: [{ label: 'Field Interaction', mobile_doctype: 'field-interaction' }],
    ccv_forms: [{ label: 'CCV - Lifting Operations', mobile_doctype: 'ccv-lifting-operations' }],
  } })
  wrapper = mount(Home, {
    attachTo: document.body,
    global: { config: { errorHandler: (error) => errors.push(error) } },
  })
  await flushPromises()
  await clickButton('Shutdown')
  await clickButton('Plant Room')
  expect(errors).toEqual([])
  expect(wrapper.text()).toContain('Inspect pump')
  expect(wrapper.text()).toContain('5th Nov 26')
  return wrapper
}

describe('Mobile location expansion', () => {
  it('opens project and area schedules in the native route', async () => {
    await openLocation(null, null, [{ key: 'gantt', label: 'Gantt', description: 'View the project schedule.' }])
    await clickButton('Area Gantt')
    expect(mocks.navigate).toHaveBeenLastCalledWith({ name: 'project-gantt', params: { project: 'PROJ-1' }, query: { area: 'AREA-1' } })
    await clickButton('Project Tools')
    await clickButton('View the project schedule.')
    expect(mocks.navigate).toHaveBeenLastCalledWith({ name: 'project-gantt', params: { project: 'PROJ-1' }, query: {} })
  })

  it.each([
    ['seconds from Frappe Time fields', 28800, 64800, '8:00am', '6:00pm'],
    ['midnight in seconds', 0, 23400, '12:00am', '6:30am'],
    ['clock strings', '08:00:00', '18:30:00', '8:00am', '6:30pm'],
    ['unpadded clock strings', '8:05:00', '0:00:00', '8:05am', '12:00am'],
  ])('keeps tasks visible with %s', async (_label, start, end, startLabel, endLabel) => {
    await openLocation(start, end)
    expect(wrapper.text()).toContain(startLabel)
    expect(wrapper.text()).toContain(endLabel)
    await clickButton('+ Form')
    expect(document.body.textContent).toContain('Field Interaction')
    await clickButton('Close')
    await clickButton('+ CCV')
    expect(document.body.textContent).toContain('CCV - Lifting Operations')
  })

  it.each([null, '', {}, [], true, -1, 86400, NaN, Infinity, 'invalid', '25:00', '08:90']) (
    'keeps the location usable when a time is missing or invalid: %j', async (value) => {
      await openLocation(value, value)
      await clickButton('Plant Room')
      expect(wrapper.text()).not.toContain('Inspect pump')
      await clickButton('Plant Room')
      expect(wrapper.text()).toContain('Inspect pump')
    }
  )
})

describe('Gantt task forms', () => {
  async function mountSchedule(query) {
    mocks.route.mockReturnValue({ params: { project: 'PROJ-1' }, query })
    mocks.api.mockResolvedValue({ message: {
      project_name: 'Shutdown',
      area_name: query.area ? 'Plant Room' : null,
      next_start: null,
      tasks: [
        { name: 'TASK-1', subject: 'Inspect pump', exp_start_date: '2026-11-05', exp_end_date: '2026-11-06' },
        { name: 'TASK-2', subject: 'Check crane' },
      ],
      task_forms: [{ label: 'Field Interaction', doctype: 'Field Interaction', mobile_doctype: 'field-interaction' }],
      ccv_forms: [{ label: 'Lifting Operations', doctype: 'CCV - Lifting Operations', mobile_doctype: 'ccv-lifting-operations' }],
    } })
    wrapper = mount(ProjectGantt, {
      attachTo: document.body,
      global: { stubs: { ProjectGanttTimeline: true } },
    })
    await flushPromises()
  }

  it('opens a new form with the task selected on the project timeline', async () => {
    await mountSchedule({})
    const timeline = wrapper.getComponent(ProjectGanttTimeline)
    timeline.vm.$emit('select', timeline.props('tasks')[0])
    await flushPromises()
    await clickButton('+ Form')
    expect(document.body.textContent).toContain('Select Form to Create')
    expect(document.body.textContent).not.toContain('Lifting Operations')
    await clickButton('Field Interaction')
    expect(mocks.navigate).toHaveBeenCalledWith({
      path: '/new/field-interaction',
      query: { link_task: 'TASK-1', project: 'PROJ-1' },
    })
  })

  it('opens a CCV for the newly selected task in an area task list', async () => {
    await mountSchedule({ area: 'AREA-1' })
    await wrapper.get('select').setValue('List')
    await clickButton('Inspect pump')
    await clickButton('+ Form')
    await clickButton('Back')
    await clickButton('Close')
    await clickButton('Check crane')
    await clickButton('+ CCV')
    expect(document.body.textContent).toContain('Select CCV to Create')
    expect(document.body.textContent).not.toContain('Field Interaction')
    await clickButton('Lifting Operations')
    expect(mocks.navigate).toHaveBeenCalledWith({
      path: '/new/ccv-lifting-operations',
      query: { link_task: 'TASK-2', project: 'PROJ-1' },
    })
  })
})
