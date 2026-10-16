export const cardTypes = ['all', 'reference', 'knowledge', 'opinion'] as const
export function preferredType(account: string) {
  try {
    const value = localStorage.getItem('selflore:card-type:' + account)
    return cardTypes.includes(value as (typeof cardTypes)[number]) ? value! : 'all'
  } catch {
    return 'all'
  }
}
export function rememberType(account: string, type: string) {
  try {
    localStorage.setItem('selflore:card-type:' + account, type)
  } catch {
    /* Browsing remains available when storage is blocked. */
  }
}
export function legacyList(search: string, opinion = false) {
  const query = new URLSearchParams(search)
  if (opinion) query.set('type', 'opinion')
  else if (!query.get('type')) query.set('type', 'all')
  return '/cards?' + query.toString()
}
