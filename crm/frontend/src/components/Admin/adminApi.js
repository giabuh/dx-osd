// Manager screens (/crm/admin): thin helpers over the mmm_custom whitelisted methods.
import { call } from 'frappe-ui'

// The text of frappe.throw, or a generic fallback.
export function errorText(error) {
  const message = error?.messages?.[0] || error?.message || ''
  if (!message) return 'Lỗi máy chủ.'
  const box = document.createElement('div')
  box.innerHTML = message
  return box.textContent.trim()
}

export async function adminCall(method, args = {}) {
  try {
    return await call(method, args)
  } catch (error) {
    throw new Error(errorText(error), { cause: error })
  }
}

export const money = (value) =>
  `${new Intl.NumberFormat('vi-VN').format(Number(value || 0))}đ`

export const displayTime = (value) =>
  value ? String(value).replace('T', ' ').slice(0, 16) : '—'

export const LEVEL_LABELS = {
  Consultant: 'Tư vấn viên',
  'Team Lead': 'Trưởng nhóm',
}
