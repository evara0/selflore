import { useParams, useSearchParams } from 'react-router-dom'
import { useData, type Card } from '../../lib/workspace'
import { QueryState } from '../../components/Common'
import CardForm from './CardForm'
import MemoEditor from './MemoEditor'

export default function Editor() {
  const { id } = useParams(),
    [search] = useSearchParams()
  const query = useData<Card>(`/cards/${id}`, !!id)
  if (id)
    return (
      <QueryState query={query}>
        {query.data &&
          (query.data.kind === 'memo' ? (
            <MemoEditor key={id} original={query.data} />
          ) : (
            <CardForm key={id} original={query.data} />
          ))}
      </QueryState>
    )
  if (search.get('kind') === 'memo') return <MemoEditor key={search.get('memo_format') || 'note'} />
  return (
    <CardForm
      key={search.get('kind') || 'knowledge'}
      initialKind={search.get('kind') || 'knowledge'}
    />
  )
}
