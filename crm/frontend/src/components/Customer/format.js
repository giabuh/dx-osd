// Sao Việt (D-122): how the customer and registration pages write dates and money.

export function dateVi(value) {
  const [y, m, d] = String(value || '')
    .slice(0, 10)
    .split('-')
  return d ? `${d}/${m}/${y}` : ''
}

export function vnd(value) {
  return (
    new Intl.NumberFormat('vi-VN').format(Math.round(Number(value) || 0)) + 'đ'
  )
}
