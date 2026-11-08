import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MyProfile from '../src/pages/MyProfile.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), navigate: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.navigate }) }))
vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({
  userFullname: ref('Test User'), userImageUrl: ref('/avatar.png'),
}) }))

const account = { full_name: 'Test User', email: 'user@example.test', phone: '', mobile_no: '0400000000' }
let wrapper
beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { wrapper?.unmount() })

describe('Read-only My profile page', () => {
  it('loads current details without caching and displays them without edit controls', async () => {
    mocks.api.mockResolvedValue({ message: { user: account, employee: {
      name: 'HR-EMP-001', employee_name: 'Test User', employee_number: '12345',
      company: 'Mine Site Support', designation: 'Advisor', date_of_joining: '2026-01-15',
    } } })
    wrapper = mount(MyProfile)
    expect(wrapper.get('[role="status"]').text()).toBe('Loading your profile…')
    await flushPromises()
    expect(mocks.api).toHaveBeenCalledWith('/api/method/verto.api.mobile.profile.get_my_profile', { cache: 'no-store' })
    for (const value of ['Test User', 'user@example.test', 'HR-EMP-001', '12345', 'Mine Site Support', 'Advisor', '0400000000', 'Not set']) {
      expect(wrapper.text()).toContain(value)
    }
    expect(wrapper.findAll('input, select, textarea, [contenteditable="true"]')).toHaveLength(0)
    expect(wrapper.findAll('button').map(button => button.text())).toEqual(['Home'])
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('TU')
    await wrapper.get('button').trigger('click')
    expect(mocks.navigate).toHaveBeenCalledWith('/')
  })

  it('shows account details for users without an Employee record', async () => {
    mocks.api.mockResolvedValue({ message: { user: account, employee: null } })
    wrapper = mount(MyProfile)
    await flushPromises()
    expect(wrapper.text()).toContain('No employee record is linked to your account.')
    expect(wrapper.text()).toContain(account.email)
    expect(wrapper.text()).not.toContain('Employment details')
  })

  it('offers a retry when loading fails and clears the error on success', async () => {
    mocks.api.mockRejectedValueOnce(new Error('Network unavailable'))
      .mockResolvedValueOnce({ message: { user: account, employee: null } })
    wrapper = mount(MyProfile)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Could not load your profile')
    await wrapper.findAll('button').find(button => button.text() === 'Try again').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain(account.email)
  })
})
