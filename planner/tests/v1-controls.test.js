import {afterEach, describe, expect, it} from 'vitest'
import {mount, flushPromises, DOMWrapper} from '@vue/test-utils'
import {nextTick} from 'vue'
import {createRouter, createMemoryHistory} from 'vue-router'
import {Combobox, DateRangePicker, Dialogs, setConfig} from 'frappe-ui'
import Header from '../src/components/MonthViewHeader.vue'
import Link from '../src/components/Link.vue'
import ProjectSpanDialog from '../src/components/ProjectSpanDialog.vue'
import {dayjs} from '../src/utils'
let wrapper, dialogs
const settle=async()=>{await flushPromises();await nextTick()}
afterEach(()=>{wrapper?.unmount();dialogs?.unmount();document.body.innerHTML=''})
describe('Frappe UI v1 integration',()=>{
  it('emits scalar filter values and date tuples while retaining period navigation',async()=>{
    setConfig('resourceFetcher',async({url})=>{
      if(url.endsWith('get_default_company'))return 'MSS'
      return [{name:'MSS'},{name:'DG'}]
    })
    wrapper=mount(Header,{attachTo:document.body,props:{firstOfMonth:dayjs('2026-09-01'),viewMode:'year'}})
    await settle()
    const company=wrapper.findAllComponents(Combobox).find(c=>c.props('label')==='Company')
    expect(company.props('modelValue')).toBe('MSS')
    company.vm.$emit('update:modelValue','DG');await settle()
    expect(wrapper.emitted('updateFilters').at(-1)[0].company).toBe('DG')
    wrapper.findComponent(DateRangePicker).vm.$emit('update:modelValue',['2026-09-01','2026-09-30']);await settle()
    expect(wrapper.emitted('updateDateRange').at(-1)[0]).toEqual({from:'2026-09-01',to:'2026-09-30'})
    await wrapper.find('[aria-label="Next period"]').trigger('click')
    expect(wrapper.emitted('addToMonth').at(-1)).toEqual([12])
  })
  it('keeps server link filters on each search and emits the selected ID',async()=>{
    const requests=[]
    setConfig('resourceFetcher',async({params})=>{requests.push(params);return [{value:'EMP-1',description:'Alex'}]})
    wrapper=mount(Link,{props:{doctype:'Employee',label:'Employee',filters:{company:'MSS'}}})
    await settle()
    expect(requests[0].filters).toEqual({company:'MSS'})
    await wrapper.setProps({filters:{company:'DG'}});await settle()
    expect(requests.at(-1).filters).toEqual({company:'DG'})
    wrapper.findComponent(Combobox).vm.$emit('update:modelValue','EMP-1');await settle()
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['EMP-1'])
  })
  it('requires the new confirmation dialog before creating tasks',async()=>{
    let saves=0
    const details={project:'PROJ-1',project_name:'Project',has_tasks:true,task_count:3,can_create_generic_tasks:true,execution_tasks:[]}
    setConfig('resourceFetcher',async({url})=>{
      if(url.endsWith('create_generic_project_tasks')){saves++;return {project_details:details,created_tasks:[{},{},{}]}}
      return details
    })
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{template:'<div />'}}]})
    await router.push('/');await router.isReady()
    dialogs=mount(Dialogs,{attachTo:document.body})
    wrapper=mount(ProjectSpanDialog,{attachTo:document.body,props:{isDialogOpen:true,modelValue:true,project:{project:'PROJ-1'}},global:{plugins:[router]}})
    await settle()
    const add=[...document.querySelectorAll('button')].find(el=>el.textContent.trim()==='Add 3 Generic Tasks')
    await new DOMWrapper(add).trigger('click');await settle()
    expect(saves).toBe(0)
    const confirmDialog=[...document.querySelectorAll('[role=dialog]')].find(el=>el.textContent.includes('Existing tasks will be preserved.'))
    expect(confirmDialog).toBeTruthy()
    const confirm=[...confirmDialog.querySelectorAll('button')].find(el=>el.textContent.trim()==='Confirm')
    await new DOMWrapper(confirm).trigger('click');await settle()
    expect(saves).toBe(1)
  })
})
