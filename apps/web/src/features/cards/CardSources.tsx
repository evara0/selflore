import { Labels } from '../../components/Selectors'
export type SourceFields = {
  sourceTitle: string
  sourceUrl: string
  locator: string
  author: string
  publisher: string
  platform: string
  published: string
}
type Props = {
  kind: string
  topics: string[]
  tags: string[]
  source: SourceFields
  onSourceChange: (field: keyof SourceFields, value: string) => void
  onLabelsChange: (topics: string[], tags: string[]) => void
}
export default function CardSources({
  kind,
  topics,
  tags,
  source,
  onSourceChange,
  onLabelsChange,
}: Props) {
  return (
    <aside className="editor-side">
      <h3>组织与来源</h3>
      <Labels kind={kind} topics={topics} tags={tags} onChange={onLabelsChange} />
      <label>
        来源标题
        <input
          value={source.sourceTitle}
          maxLength={200}
          onChange={(e) => onSourceChange('sourceTitle', e.target.value)}
        />
      </label>
      <label>
        来源链接
        <input
          type="url"
          value={source.sourceUrl}
          onChange={(e) => onSourceChange('sourceUrl', e.target.value)}
          placeholder="https://"
        />
      </label>
      <label>
        页码 / 定位
        <input
          value={source.locator}
          maxLength={200}
          onChange={(e) => onSourceChange('locator', e.target.value)}
        />
      </label>
      <label>
        来源作者
        <input
          value={source.author}
          maxLength={200}
          onChange={(e) => onSourceChange('author', e.target.value)}
        />
      </label>
      <label>
        发布／转载者
        <input
          value={source.publisher}
          maxLength={200}
          onChange={(e) => onSourceChange('publisher', e.target.value)}
        />
      </label>
      <label>
        来源平台
        <input
          value={source.platform}
          maxLength={80}
          onChange={(e) => onSourceChange('platform', e.target.value)}
        />
      </label>
      <label>
        发布日期
        <input
          type="date"
          value={source.published}
          onChange={(e) => onSourceChange('published', e.target.value)}
        />
      </label>
      <p className="muted">未知来源可留空。引用使用稳定 ID。修改标题后，连接仍然存在。</p>
    </aside>
  )
}
