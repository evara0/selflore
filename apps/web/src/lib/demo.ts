import type { Card, Collection, Label } from './workspace'

export const DEMO_CACHE_KEY = 'guest-demo-v4'
export const demoId = (n: number) => `de000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const knowledgeTopics: Label[] = [
  { id: demoId(101), name: '学习方法', kind: 'knowledge' },
  { id: demoId(102), name: '科学与思考', kind: 'knowledge' },
]
const opinionTopics: Label[] = [
  { id: demoId(103), name: '知识管理', kind: 'opinion' },
  { id: demoId(104), name: '日常思考', kind: 'opinion' },
]
const referenceTopics: Label[] = [{ id: demoId(105), name: '阅读材料', kind: 'reference' }]
const tags: Label[] = [
  { id: demoId(201), name: '主动回忆' },
  { id: demoId(202), name: '卡片笔记' },
  { id: demoId(203), name: '思维工具' },
]
const examples = [
  [
    '主动回忆为什么有效？',
    'qa',
    '什么是主动回忆？',
    '主动回忆是先不看材料，尝试从记忆中提取答案，再检查和修正。提取本身也是学习的一部分。',
  ],
  [
    '间隔重复的基本原则',
    'qa',
    '为什么要把复习分散到不同时间？',
    '在逐渐遗忘时重新提取，比连续重复阅读更有助于长期记忆。具体间隔随掌握程度调整。',
  ],
  [
    '用填空记住学习过程',
    'cloze',
    '',
    '学习不只是输入，还需要{{c1::主动提取::学习动作}}和{{c2::及时反馈::修正动作}}。',
  ],
  [
    '相关性与因果性',
    'qa',
    '两个现象一起发生，就说明一个导致另一个吗？',
    '不一定。它们可能受到共同因素影响，也可能只是巧合；需要更多证据建立因果关系。',
  ],
  [
    '什么是机会成本？',
    'qa',
    '选择一件事时，机会成本指什么？',
    '机会成本是为了该选择而放弃的最佳替代方案的价值。它提醒我们同时考虑放弃了什么。',
  ],
  [
    '费曼学习法的提醒',
    'qa',
    '把概念讲给初学者时，为什么能发现理解中的空白？',
    '解释需要把概念、关系和例子组织起来。说不清的地方往往需要进一步查证和理解。',
  ],
  [
    '解释一个概念时卡住了',
    'opinion',
    '',
    `今天试着向朋友解释间隔重复，讲到“为什么要拉开时间”时卡住了。我会做题，却还说不清理由。\n\n例如 [[${demoId(1)}|主动回忆]] 可以帮我检查自己是否记得；下一次还要试着把理由讲清楚。`,
  ],
  [
    '读完一章后合上书',
    'opinion',
    '',
    `昨晚读完一章，合上书后只复述出了两个例子，没说出作者的结论。今天重读时，先补上结论和支持它的证据。\n\n这与 [[${demoId(6)}|费曼学习法]] 中“讲给初学者”的做法相似。我也记下了上次 [[${demoId(7)}|解释卡住的经历]]。`,
  ],
  [
    '先把购物车放一晚',
    'opinion',
    '',
    '昨晚把一盏台灯放进购物车，今天发现桌上那盏仍然够用。先等一晚，让我分清了想换新的和实际需要。',
  ],
] as const
const cards: Card[] = examples.map(([title, form, question, content], index) => {
  const kind = form === 'opinion' ? 'opinion' : 'knowledge'
  const topic =
    kind === 'knowledge' ? knowledgeTopics[index < 3 ? 0 : 1] : opinionTopics[index === 8 ? 1 : 0]
  const tag = tags[index < 3 ? 0 : kind === 'opinion' ? 1 : 2]
  return {
    id: demoId(index + 1),
    title,
    code: `示例-${String(index + 1).padStart(3, '0')}`,
    kind,
    form: form === 'opinion' ? null : form,
    question_md: form === 'qa' ? question : undefined,
    answer_md: form === 'qa' ? content : undefined,
    body_md: form !== 'qa' ? content : undefined,
    excerpt:
      form === 'qa'
        ? question
        : content
            .replace(/\{\{c\d+::[^{}]+\}\}/g, '【…】')
            .replace(/\[\[[^\]]+\]\]/g, '关联卡片')
            .slice(0, 100),
    lifecycle: 'active',
    revision: 1,
    is_bookmarked: index === 0 || index === 6,
    processing_state: index === 8 ? 'inbox' : 'organized',
    tags: [tag],
    topics: [topic],
    tag_ids: [tag.id],
    topic_ids: [topic.id],
    link_count: index === 6 ? 1 : index === 7 ? 2 : 0,
    backlink_count: index === 0 || index === 5 || index === 6 ? 1 : 0,
    updated_at: `2026-10-08T0${index}:00:00Z`,
  }
})
cards.push({
  id: demoId(10),
  title: '一周借阅记录',
  code: '示例-010',
  kind: 'reference',
  form: null,
  body_md: '示例表格记录了三个日期的借阅数量，数据为虚构。',
  note_md: '周三的借阅量最多，但只有一周记录，还不能判断每周是否如此。',
  excerpt: '三个日期的借阅数量，附个人观察。',
  source_author: 'SelfLore演示',
  source_platform: '示例',
  attachments: [
    {
      id: demoId(401),
      caption: '一周借阅记录（虚构数据）',
      alt_text: '周一 12 本、周三 21 本、周五 16 本的借阅记录示例表',
      demo_url: '/demo/reference.svg',
    },
  ],
  lifecycle: 'active',
  revision: 1,
  is_bookmarked: false,
  processing_state: 'inbox',
  topics: referenceTopics,
  topic_ids: [demoId(105)],
  tags: [],
  tag_ids: [],
  updated_at: '2026-10-12T00:00:00Z',
})
cards.push({
  id: demoId(11),
  title: '下次读书时记得问',
  code: '示例-011',
  kind: 'memo',
  form: null,
  memo_format: 'note',
  body_md: '作者的结论由哪些证据支持？',
  excerpt: '作者的结论由哪些证据支持？',
  lifecycle: 'active',
  revision: 1,
  processing_state: 'inbox',
  is_bookmarked: false,
  tags: [],
  topics: [],
  tag_ids: [],
  topic_ids: [],
  memo_items: [],
})
cards.push({
  id: demoId(12),
  title: '本周待学清单',
  code: '示例-012',
  kind: 'memo',
  form: null,
  memo_format: 'checklist',
  excerpt: '阅读与核实资料',
  lifecycle: 'active',
  revision: 1,
  processing_state: 'inbox',
  is_bookmarked: false,
  tags: [],
  topics: [],
  tag_ids: [],
  topic_ids: [],
  memo_progress: { total: 2, completed: 1 },
  memo_items: [
    {
      id: demoId(501),
      text: '阅读主动回忆的方法',
      is_completed: true,
      completed_at: '2026-10-15T00:00:00Z',
      target_ids: [demoId(1)],
      targets: [{ id: demoId(1), title: cards[0].title, kind: 'knowledge', lifecycle: 'active' }],
    },
    {
      id: demoId(502),
      text: '核实借阅记录的范围',
      is_completed: false,
      target_ids: [demoId(10)],
      targets: [{ id: demoId(10), title: cards[9].title, kind: 'reference', lifecycle: 'active' }],
    },
  ],
})
const collections: Collection[] = [
  {
    id: demoId(301),
    title: '读书时记下的几张卡片',
    description_md: '记忆方法、解释概念和读后复述。',
    cover_style: 'curve',
    cover_color: 'sage',
    is_favorite: true,
    is_pinned: true,
    revision: 1,
    lifecycle: 'active',
    total_items: 6,
    available_items: 6,
    knowledge_count: 3,
    opinion_count: 2,
    memo_count: 1,
  },
  {
    id: demoId(302),
    title: '日常判断',
    description_md: '因果、取舍与一次购物记录。',
    cover_style: 'radial',
    cover_color: 'clay',
    is_favorite: false,
    is_pinned: true,
    revision: 1,
    lifecycle: 'active',
    total_items: 5,
    available_items: 5,
    knowledge_count: 3,
    opinion_count: 1,
    reference_count: 1,
  },
]
const memberIds: Record<string, number[]> = {
  [demoId(301)]: [1, 3, 7, 6, 8, 12],
  [demoId(302)]: [4, 5, 6, 9, 10],
}
const outgoing: Record<string, number[]> = { [demoId(7)]: [1], [demoId(8)]: [6, 7] }
function page<T>(items: T[], query: URLSearchParams, defaultLimit = 12) {
  const limit = Math.max(1, Math.min(100, Number(query.get('limit')) || defaultLimit)),
    offset = Math.max(0, Number(query.get('offset')) || 0)
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset }
}
function related(card: Card) {
  return {
    id: card.id,
    title: card.title,
    kind: card.kind,
    lifecycle: card.lifecycle,
    origins: ['inline'],
  }
}
function read(path: string): unknown {
  const url = new URL(path, 'https://demo.invalid'),
    route = url.pathname,
    query = url.searchParams
  if (route === '/cards/summary')
    return { knowledge: 6, opinions: 3, references: 1, memos: 2, inbox: 2 }
  if (route === '/memo-items')
    return page(
      cards
        .filter((c) => c.kind === 'memo' && c.lifecycle === 'active')
        .flatMap((c) =>
          (c.memo_items || [])
            .filter(
              (i) =>
                i.is_completed === (query.get('is_completed') === 'true') &&
                (c.title + ' ' + i.text).includes(query.get('q') || ''),
            )
            .map((i) => ({ ...i, memo_card_id: c.id, memo_title: c.title, revision: c.revision })),
        ),
      query,
    )
  if (route === '/cards') {
    let items = cards.filter(
      (card) =>
        (!query.get('kind') || card.kind === query.get('kind')) &&
        (!query.get('memo_format') || card.memo_format === query.get('memo_format')) &&
        (!query.get('kinds') || query.get('kinds')!.split(',').includes(card.kind)) &&
        (!query.get('lifecycle') || card.lifecycle === query.get('lifecycle')) &&
        (!query.get('topic_id') || card.topic_ids.includes(query.get('topic_id')!)) &&
        (!query.get('tag_id') || card.tag_ids.includes(query.get('tag_id')!)) &&
        (query.get('is_bookmarked') !== 'true' || card.is_bookmarked) &&
        (!query.get('processing_state') ||
          card.processing_state === query.get('processing_state')) &&
        `${card.title} ${card.question_md || ''} ${card.body_md || ''} ${(card.note_md || '') + ' ' + (card.memo_items || []).map((i) => i.text).join(' ')} ${card.source_author || ''} ${card.answer_md || ''} ${card.tags.map((t) => t.name).join(' ')}`.includes(
          query.get('q') || '',
        ),
    )
    items = [...items].sort((a, b) =>
      query.get('sort') === 'code_asc'
        ? a.code.localeCompare(b.code)
        : query.get('sort') === 'connections_desc'
          ? (b.link_count || 0) +
            (b.backlink_count || 0) -
            (a.link_count || 0) -
            (a.backlink_count || 0)
          : b.id.localeCompare(a.id),
    )
    return page(
      items.map(({ question_md: _q, answer_md: _a, body_md: _b, ...summary }) => summary),
      query,
    )
  }
  if (route === '/topics')
    return {
      items: (query.get('kind') === 'knowledge'
        ? knowledgeTopics
        : query.get('kind') === 'reference'
          ? referenceTopics
          : query.get('kind') === 'opinion'
            ? opinionTopics
            : [...knowledgeTopics, ...opinionTopics, ...referenceTopics]
      ).map((t) => ({ ...t, card_count: cards.filter((c) => c.topic_ids.includes(t.id)).length })),
    }
  if (route === '/tags') return { items: tags }
  const cardMatch = /^\/cards\/([^/]+)(\/links)?$/.exec(route)
  if (cardMatch) {
    const card = cards.find((c) => c.id === cardMatch[1])
    if (!card) throw new Error('这张演示卡片不存在，请返回演示知识库。')
    return cardMatch[2]
      ? {
          outgoing: (outgoing[card.id] || []).map((n) => related(cards[n - 1])),
          incoming: cards
            .filter((c) => outgoing[c.id]?.includes(cards.indexOf(card) + 1))
            .map(related),
        }
      : card
  }
  if (route === '/reviews/summary')
    return {
      due_units: 3,
      new_units: 4,
      today_completed: 5,
      mastered_cards: 2,
      daily_review_goal: 20,
    }
  if (route === '/collections')
    return page(
      collections.filter(
        (c) =>
          (query.get('is_favorite') !== 'true' || c.is_favorite) &&
          c.title.includes(query.get('q') || ''),
      ),
      query,
    )
  const collectionMatch = /^\/collections\/([^/]+)(\/items)?$/.exec(route)
  if (collectionMatch) {
    const collection = collections.find((c) => c.id === collectionMatch[1])
    if (!collection) throw new Error('这个演示合集不存在，请返回合集列表。')
    return collectionMatch[2]
      ? {
          revision: 1,
          items: memberIds[collection.id].map((n, i) => ({
            ...cards[n - 1],
            item_id: demoId(Number(collection.id.slice(-3)) * 10 + i),
            position: i,
          })),
        }
      : collection
  }
  if (route === '/me/profile')
    return {
      display_name: '演示账号',
      username: 'demo',
      bio: '只读示例账号。',
      avatar_color: 'sage',
      interests: ['学习方法', '卡片笔记', '日常思考'],
      timezone: 'Asia/Shanghai',
      revision: 1,
      daily_new_limit: 20,
      daily_review_goal: 20,
    }
  if (route === '/me/summary')
    return { knowledge: 6, opinions: 3, references: 1, memos: 2, collections: 2, streak: 3 }
  if (route === '/me/pinned-collections') return { items: collections }
  if (route === '/me/activity')
    return page(
      cards
        .filter((c) => !query.get('kind') || c.kind === query.get('kind'))
        .slice()
        .reverse()
        .map((c) => ({
          id: `sample-${c.id}`,
          card_id: c.id,
          kind: c.kind,
          lifecycle: c.lifecycle,
          event_kind: 'card_created',
          entity_title: c.title,
          occurred_at: c.updated_at,
        })),
      query,
      8,
    )
  if (route === '/me/heatmap') {
    const today = new Date(
      new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' }) + 'T00:00:00Z',
    )
    const start = new Date(today)
    start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7) - 77)
    return {
      timezone: 'Asia/Shanghai',
      days: Array.from({ length: 84 }, (_, i) => {
        const d = new Date(start)
        d.setUTCDate(d.getUTCDate() + i)
        return {
          date: d.toISOString().slice(0, 10),
          count: d > today ? 0 : i % 5 === 0 ? 3 : i % 3 === 0 ? 1 : 0,
          is_future: d > today,
        }
      }),
    }
  }
  throw new Error('此功能需要登录后使用。')
}
export function readDemo<T>(path: string): T {
  // Callers receive a copy; UI operations cannot mutate the shared sample dataset.
  return structuredClone(read(path)) as T
}
