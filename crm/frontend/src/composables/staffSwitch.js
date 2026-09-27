// Demo helper: a System Manager views the CRM as a consultant (mmm_custom.staff_switch).
import { call, createResource } from 'frappe-ui'

export const staffSwitch = createResource({
  url: 'mmm_custom.staff_switch.state',
  auto: true,
})

function errorText(error) {
  return error?.messages?.[0] || error?.message || 'Không đổi được tài khoản.'
}

// A new session cookie is set by the server; reload so every store starts from it.
export async function switchToStaff(user) {
  try {
    await call('mmm_custom.staff_switch.switch_to', { user })
  } catch (error) {
    throw new Error(errorText(error), { cause: error })
  }
  window.location.href = '/crm/leads'
}

export async function switchBack() {
  try {
    await call('mmm_custom.staff_switch.switch_back')
  } catch (error) {
    throw new Error(errorText(error), { cause: error })
  }
  window.location.href = '/crm/admin/staff'
}
