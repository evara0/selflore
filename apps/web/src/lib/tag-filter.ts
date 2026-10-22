export function tagQuery(search: URLSearchParams) {
  const result = new URLSearchParams()
  const ids = [...new Set(search.getAll('tag_ids'))].sort()
  if (ids.length) {
    ids.forEach((id) => result.append('tag_ids', id))
    result.set('tag_match', search.get('tag_match') || 'all')
  }
  // Preserve mixed legacy conditions: the API rejects ambiguity instead of widening results.
  if (search.get('topic')) result.set('topic_id', search.get('topic')!)
  if (search.get('tag')) result.set('tag_id', search.get('tag')!)
  return result.toString()
}
