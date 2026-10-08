import type { Card, Collection, Label } from './workspace'

export const DEMO_CACHE_KEY = 'guest-demo-v1'
export const demoId = (n: number) => `de000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const knowledgeTopics: Label[] = [{ id: demoId(101), name: '学习方法', kind: 'knowledge' }, { id: demoId(102), name: '科学与思考', kind: 'knowledge' }]
const opinionTopics: Label[] = [{ id: demoId(103), name: '知识管理', kind: 'opinion' }, { id: demoId(104), name: '日常思考', kind: 'opinion' }]
const tags: Label[] = [{ id: demoId(201), name: '主动回忆' }, { id: demoId(202), name: '卡片笔记' }, { id: demoId(203), name: '思维工具' }]
const examples = [
  ['主动回忆为什么有效？', 'qa', '什么是主动回忆？', '主动回忆是先不看材料，尝试从记忆中提取答案，再检查和修正。提取本身也是学习的一部分。'],
  ['间隔重复的基本原则', 'qa', '为什么要把复习分散到不同时间？', '在逐渐遗忘时重新提取，比连续重复阅读更有助于长期记忆。具体间隔随掌握程度调整。'],
  ['用填空记住学习过程', 'cloze', '', '学习不只是输入，还需要{{c1::主动提取::学习动作}}和{{c2::及时反馈::修正动作}}。'],
  ['相关性与因果性', 'qa', '两个现象一起发生，就说明一个导致另一个吗？', '不一定。它们可能受到共同因素影响，也可能只是巧合；需要更多证据建立因果关系。'],
  ['什么是机会成本？', 'qa', '选择一件事时，机会成本指什么？', '机会成本是为了该选择而放弃的最佳替代方案的价值。它提醒我们同时考虑放弃了什么。'],
  ['费曼学习法的提醒', 'qa', '把概念讲给初学者时，为什么能发现理解中的空白？', '解释需要把概念、关系和例子组织起来。说不清的地方往往需要进一步查证和理解。'],
  ['笔记的价值在于连接', 'opinion', '', `一张笔记不必容纳所有信息。把一个想法说清楚，再连接已有知识，能让它持续生长。\n\n例如 [[${demoId(1)}|主动回忆]] 提醒我：笔记也应帮助我重新思考，而不只是储存文字。`],
  ['让阅读留下自己的问题', 'opinion', '', `读完一段内容后，先写下自己的问题，再整理答案。问题让阅读从接收转向探索。\n\n这与 [[${demoId(6)}|费曼学习法]] 的解释过程相呼应，也能连接到 [[${demoId(7)}|笔记的连接]]。`],
  ['给思考留一点空白', 'opinion', '', '有时不急着把所有笔记归类，反而能发现意外的连接。定期回看待整理的想法，让结构随着理解慢慢形成。'],
] as const
const cards: Card[] = examples.map(([title, form, question, content], index) => {
  const kind = form === 'opinion' ? 'opinion' : 'knowledge'
  const topic = kind === 'knowledge' ? knowledgeTopics[index < 3 ? 0 : 1] : opinionTopics[index === 8 ? 1 : 0]
  const tag = tags[index < 3 ? 0 : kind === 'opinion' ? 1 : 2]
  return { id: demoId(index + 1), title, code: `示例-${String(index + 1).padStart(3, '0')}`, kind, form: form === 'opinion' ? null : form,
    question_md: form === 'qa' ? question : undefined, answer_md: form === 'qa' ? content : undefined, body_md: form !== 'qa' ? content : undefined,
    excerpt: form === 'qa' ? question : content.replace(/\{\{c\d+::[^{}]+\}\}/g, '【…】').replace(/\[\[[^\]]+\]\]/g, '关联卡片').slice(0, 100),
    lifecycle: 'active', revision: 1, is_bookmarked: index === 0 || index === 6, processing_state: index === 8 ? 'inbox' : 'organized',
    tags: [tag], topics: [topic], tag_ids: [tag.id], topic_ids: [topic.id], link_count: index === 6 ? 1 : index === 7 ? 2 : 0,
    backlink_count: index === 0 || index === 5 || index === 6 ? 1 : 0, updated_at: `2026-10-08T0${index}:00:00Z` }
})
const collections: Collection[] = [
  { id: demoId(301), title: '学习与思考入门', description_md: '从知识到观点，体验一段混合卡片阅读。', cover_style: 'curve', cover_color: 'sage', is_favorite: true, is_pinned: true, revision: 1, lifecycle: 'active', total_items: 5, available_items: 5, knowledge_count: 3, opinion_count: 2 },
  { id: demoId(302), title: '日常思维工具', description_md: '用几个问题，重新看看日常的选择与判断。', cover_style: 'radial', cover_color: 'clay', is_favorite: false, is_pinned: true, revision: 1, lifecycle: 'active', total_items: 4, available_items: 4, knowledge_count: 3, opinion_count: 1 },
]
const memberIds: Record<string, number[]> = { [demoId(301)]: [1, 3, 7, 6, 8], [demoId(302)]: [4, 5, 6, 9] }
const outgoing: Record<string, number[]> = { [demoId(7)]: [1], [demoId(8)]: [6, 7] }
function page<T>(items: T[], query: URLSearchParams, defaultLimit = 12) {
  const limit = Math.max(1, Math.min(100, Number(query.get('limit')) || defaultLimit)), offset = Math.max(0, Number(query.get('offset')) || 0)
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset }
}
function related(card: Card) { return { id: card.id, title: card.title, kind: card.kind, lifecycle: card.lifecycle, origins: ['inline'] } }
function read(path: string): unknown {
  const url = new URL(path, 'https://demo.invalid'), route = url.pathname, query = url.searchParams
  if (route === '/cards/summary') return { knowledge: 6, opinions: 3, inbox: 1 }
  if (route === '/cards') {
    let items = cards.filter(card => (!query.get('kind') || card.kind === query.get('kind')) && (!query.get('lifecycle') || card.lifecycle === query.get('lifecycle')) &&
      (!query.get('topic_id') || card.topic_ids.includes(query.get('topic_id')!)) && (!query.get('tag_id') || card.tag_ids.includes(query.get('tag_id')!)) &&
      (query.get('is_bookmarked') !== 'true' || card.is_bookmarked) && (!query.get('processing_state') || card.processing_state === query.get('processing_state')) &&
      `${card.title} ${card.question_md || ''} ${card.body_md || ''} ${card.answer_md || ''} ${card.tags.map(t => t.name).join(' ')}`.includes(query.get('q') || ''))
    items = [...items].sort((a, b) => query.get('sort') === 'code_asc' ? a.code.localeCompare(b.code) : query.get('sort') === 'connections_desc' ? (b.link_count || 0) + (b.backlink_count || 0) - (a.link_count || 0) - (a.backlink_count || 0) : b.id.localeCompare(a.id))
    return page(items.map(({ question_md: _q, answer_md: _a, body_md: _b, ...summary }) => summary), query)
  }
  if (route === '/topics') return { items: (query.get('kind') === 'knowledge' ? knowledgeTopics : opinionTopics).map(t => ({ ...t, card_count: cards.filter(c => c.topic_ids.includes(t.id)).length })) }
  if (route === '/tags') return { items: tags }
  const cardMatch = /^\/cards\/([^/]+)(\/links)?$/.exec(route)
  if (cardMatch) {
    const card = cards.find(c => c.id === cardMatch[1]); if (!card) throw new Error('这张演示卡片不存在，请返回演示知识库。')
    return cardMatch[2] ? { outgoing: (outgoing[card.id] || []).map(n => related(cards[n - 1])), incoming: cards.filter(c => outgoing[c.id]?.includes(cards.indexOf(card) + 1)).map(related) } : card
  }
  if (route === '/reviews/summary') return { due_units: 3, new_units: 4, today_completed: 5, mastered_cards: 2, daily_review_goal: 20 }
  if (route === '/collections') return page(collections.filter(c => (query.get('is_favorite') !== 'true' || c.is_favorite) && c.title.includes(query.get('q') || '')), query)
  const collectionMatch = /^\/collections\/([^/]+)(\/items)?$/.exec(route)
  if (collectionMatch) {
    const collection = collections.find(c => c.id === collectionMatch[1]); if (!collection) throw new Error('这个演示合集不存在，请返回合集列表。')
    return collectionMatch[2] ? { revision: 1, items: memberIds[collection.id].map((n, i) => ({ ...cards[n - 1], item_id: demoId(Number(collection.id.slice(-3)) * 10 + i), position: i })) } : collection
  }
  if (route === '/me/profile') return { display_name: '演示账号', username: 'demo', bio: '这是只读演示资料。卡片、数量和学习足迹均为示例，登录后开始建立你自己的空间。', avatar_color: 'sage', interests: ['学习方法', '卡片笔记', '日常思考'], timezone: 'Asia/Shanghai', revision: 1, daily_new_limit: 20, daily_review_goal: 20 }
  if (route === '/me/summary') return { knowledge: 6, opinions: 3, collections: 2, streak: 3 }
  if (route === '/me/pinned-collections') return { items: collections }
  if (route === '/me/activity') return page(cards.filter(c => !query.get('kind') || c.kind === query.get('kind')).slice().reverse().map(c => ({ id: `sample-${c.id}`, card_id: c.id, kind: c.kind, lifecycle: c.lifecycle, event_kind: 'card_created', entity_title: c.title, occurred_at: c.updated_at })), query, 8)
  if (route === '/me/heatmap') {
    const today = new Date(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' }) + 'T00:00:00Z')
    const start = new Date(today); start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7) - 77)
    return { timezone: 'Asia/Shanghai', days: Array.from({ length: 84 }, (_, i) => { const d = new Date(start); d.setUTCDate(d.getUTCDate() + i); return { date: d.toISOString().slice(0, 10), count: d > today ? 0 : i % 5 === 0 ? 3 : i % 3 === 0 ? 1 : 0, is_future: d > today } }) }
  }
  throw new Error('此功能需要登录后使用。')
}
export function readDemo<T>(path: string): T {
  // Callers receive a copy; UI operations cannot mutate the shared sample dataset.
  return structuredClone(read(path)) as T
}
