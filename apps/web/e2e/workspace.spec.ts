import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir } from 'node:fs/promises'

const base = 'http://127.0.0.1:24568', password = 'browser-isolated-password-123'
const shots = '../../docs/design/card-navigation-v1/implemented'
test.describe.configure({ mode: 'serial' })
let username: string, token: string, knowledgeId: string, opinionId: string, collectionId: string
test.beforeAll(async () => {
  if (process.env.SELFLORE_TEST_ISOLATED !== '1') throw new Error('Only run against the explicitly isolated 6179 database / 24568 test server.')
  await mkdir(shots, { recursive: true })
})
async function login(page: Page) {
  await page.goto('/knowledge')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('dialog').getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('button', { name: new RegExp(username) })).toBeVisible()
}
async function api(request: APIRequestContext, path: string, body: object, method = 'POST') {
  const response = await request.fetch(base + '/api' + path, { method, data: body, headers: { Origin: base, 'X-CSRF-Token': token } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
test('real creation, stable reference, mixed reader, rating and personal summary', async ({ page, request }) => {
  username = 'garden_' + randomUUID().slice(0, 8)
  expect((await request.post(base + '/api/auth/register', { data: { username, password }, headers: { Origin: base } })).status()).toBe(201)
  await login(page)
  await page.getByRole('link', { name: '＋ 新建', exact: true }).click()
  await page.getByLabel('标题', { exact: true }).fill('主动回忆为什么有效？')
  await page.getByLabel('问题', { exact: true }).fill('为什么主动提取比重复阅读更能巩固记忆？')
  await page.getByLabel('答案', { exact: true }).fill('主动提取训练了知识的检索路径，也暴露了理解中的空缺。')
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page).toHaveURL(/knowledge\/cards\//)
  knowledgeId = page.url().split('/').pop()!
  await expect(page.getByText('主动提取训练了知识的检索路径，也暴露了理解中的空缺。')).toHaveCount(0)
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  await expect(page.getByText('主动提取训练了知识的检索路径，也暴露了理解中的空缺。')).toBeVisible()
  await page.goto('/new?kind=opinion')
  await page.getByLabel('标题', { exact: true }).fill('把学习变成一场与自己的对话')
  await page.getByLabel('观点正文', { exact: true }).fill('知识只有经过主动提取，才逐渐成为可用的理解。')
  await page.getByRole('button', { name: '＋ 插入卡片引用' }).click()
  await page.getByRole('button', { name: /主动回忆为什么有效？/ }).click()
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page).toHaveURL(/opinions\?card=/)
  opinionId = new URL(page.url()).searchParams.get('card')!
  await expect(page.locator('.opinion-detail').getByRole('link', { name: '主动回忆为什么有效？', exact: true }).first()).toBeVisible()
  await page.goto('/collections/new')
  await page.getByLabel('合集名称').fill('学会学习')
  await page.getByLabel('合集描述').fill('关于记忆、理解与学习方法的一次小小探索。')
  await page.getByRole('button', { name: '保存合集' }).click()
  await expect(page).toHaveURL(/collections\/[0-9a-f-]+$/)
  collectionId = page.url().split('/').pop()!
  for (const title of ['主动回忆为什么有效？', '把学习变成一场与自己的对话']) {
    await page.getByRole('button', { name: '＋ 添加卡片' }).click()
    await page.locator('.picker-results').getByRole('button', { name: new RegExp(title.replace('？', '.')) }).click()
    await expect(page.locator('.directory-row')).toHaveCount(title.startsWith('主动') ? 1 : 2)
  }
  await page.getByRole('button', { name: '翻阅卡片', exact: true }).click()
  await expect(page.locator('.reader-card h2')).toHaveText('主动回忆为什么有效？')
  await expect(page.getByRole('button', { name: '← 上一张' })).toBeDisabled()
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  await page.getByRole('button', { name: '下一张 →' }).click()
  await expect(page.locator('.reader-card h2')).toHaveText('把学习变成一场与自己的对话')
  await expect(page.getByRole('button', { name: '良好', exact: false })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '下一张 →' })).toBeDisabled()
  await page.reload()
  await expect(page.locator('.reader-card h2')).toHaveText('把学习变成一场与自己的对话')
  await page.getByRole('button', { name: '置顶到主页' }).click()
  await expect(page.getByRole('button', { name: '取消主页置顶' })).toBeVisible()
  await page.goto('/knowledge/review')
  await expect(page.getByRole('button', { name: /良好/ })).toHaveCount(0)
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  await page.getByRole('button', { name: /良好/ }).click()
  await expect(page.getByText('本轮已完成 1 个复习单元')).toBeVisible()
  await page.goto('/me')
  await expect(page.locator('.stats-grid .stat').first()).toContainText('1')
  await expect(page.locator('.heat-cell:not(.heat-legend .heat-cell)')).toHaveCount(84)
  await expect(page.locator('.pinned-row')).toContainText('学会学习')
  // Seed additional private sample content only in this disposable test account for visual QA.
  const cookies = await page.context().cookies(); await request.storageState();
  await request.post(base + '/api/auth/login', { data: { username, password }, headers: { Origin: base } })
  token = (await (await request.get(base + '/api/auth/me')).json()).csrf_token
  expect(cookies.some(c => c.name.startsWith('selflore_session'))).toBeTruthy()
  const topic = await api(request, '/topics', { kind: 'knowledge', name: '认知与学习' })
  const tag = await api(request, '/tags', { name: '学习方法' })
  const samples = [['间隔重复的核心是什么？', '在记忆即将淡忘时再次回忆。'], ['什么是费曼学习法？', '用简单的语言解释复杂概念。'], ['睡眠如何影响记忆？', '睡眠参与记忆的整合与巩固。'], ['工作记忆与长期记忆', '工作记忆容量有限，长期记忆帮助组织信息。'], ['反馈为什么如此重要？', '及时反馈使我们看见错误，调整下一次尝试。']]
  for (const [title, answer] of samples) await api(request, '/cards', { kind: 'knowledge', form: 'qa', title, question_md: title, answer_md: answer, topic_ids: [topic.id], tag_ids: [tag.id], client_request_id: randomUUID() })
  for (const [title, body] of [['好的问题，比答案更长久', '一个有生命力的问题，会不断引导我们重新观察。'], ['笔记是思考的外部空间', '把想法放到纸上，才能看见它们之间的距离。']]) await api(request, '/cards', { kind: 'opinion', title, body_md: body, tag_ids: [tag.id], client_request_id: randomUUID() })
})
test('four actual pages, mobile navigation, failure recovery and cache isolation', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 1586, height: 992 })
  for (const [path, file] of [['/knowledge', '01-knowledge'], [`/opinions?card=${opinionId}`, '02-opinions'], [`/collections/${collectionId}?view=read`, '03-collections'], ['/me', '04-profile']]) {
    await page.goto(path); await expect(page.locator('.state[role="status"]')).toHaveCount(0); await page.screenshot({ path: shots + '/' + file + '.png', fullPage: true })
  }
  await page.setViewportSize({ width: 390, height: 844 })
  for (const path of ['/knowledge', `/opinions?card=${opinionId}`, `/collections/${collectionId}?view=read`, '/me']) {
    await page.goto(path); await expect(page.locator('.state[role="status"]')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await expect(page.getByRole('navigation', { name: '移动端导航' })).toBeVisible()
  }
  await page.screenshot({ path: shots + '/05-profile-mobile.png', fullPage: true })
  await page.getByRole('navigation', { name: '移动端导航' }).getByRole('link', { name: '知识', exact: true }).tap()
  await expect(page.locator('.flashcard')).toHaveCount(6)
  await page.locator('.flashcard').first().getByRole('button', { name: /查看答案/ }).tap()
  await expect(page.locator('.flash-answer')).toBeVisible()
  await page.goto(`/opinions?card=${opinionId}`)
  await page.getByRole('button', { name: '← 返回观点列表' }).click()
  await expect(page.locator('.opinion-list')).toBeVisible()
  await page.route('**/api/cards?*', route => route.abort())
  await page.goto('/knowledge?q=网络检查')
  await expect(page.getByRole('alert')).toBeVisible()
  await page.unroute('**/api/cards?*')
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByText('这里还没有卡片')).toBeVisible()
  await page.goto('/settings')
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  await expect(page.locator(`a[href='/knowledge/cards/${knowledgeId}']`)).toHaveCount(0)
  await page.goto(`/knowledge/cards/${knowledgeId}`)
  await expect(page.getByText('演示空间 · 只读')).toBeVisible()
  await expect(page.getByText('这张演示卡片不存在，请返回演示知识库。')).toBeVisible()
})
test('edit conflicts retain input and unsaved navigation requires a decision', async ({ page, request }) => {
  await login(page)
  await request.post(base + '/api/auth/login', { data: { username, password }, headers: { Origin: base } })
  token = (await (await request.get(base + '/api/auth/me')).json()).csrf_token
  await page.goto(`/cards/${knowledgeId}/edit`)
  await page.getByLabel('标题', { exact: true }).fill('保留在编辑器中的草稿')
  const current = await (await request.get(base + '/api/cards/' + knowledgeId)).json()
  await api(request, '/cards/' + knowledgeId, { expected_revision: current.revision, title: '另一个窗口的新标题' }, 'PATCH')
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page.getByLabel('标题', { exact: true })).toHaveValue('保留在编辑器中的草稿')
  await expect(page.getByRole('button', { name: '核对后使用最新版本号' })).toBeVisible()
  // Native history navigation uses the same unsaved-input decision as in-app links.
  page.once('dialog', dialog => dialog.dismiss())
  await page.evaluate(() => history.back())
  await expect(page).toHaveURL(/\/edit$/)
  page.once('dialog', dialog => dialog.dismiss())
  await page.getByRole('link', { name: '取消', exact: true }).click()
  await expect(page).toHaveURL(/\/edit$/)
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('link', { name: '取消', exact: true }).click()
  await expect(page).toHaveURL(/knowledge\/cards\//)
})
test('cloze reader, stable random order and input keyboard isolation', async ({ page, request }) => {
  await login(page)
  await request.post(base + '/api/auth/login', { data: { username, password }, headers: { Origin: base } })
  token = (await (await request.get(base + '/api/auth/me')).json()).csrf_token
  const cloze = await api(request, '/cards', { client_request_id: randomUUID(), title: '填空阅读示例', kind: 'knowledge', form: 'cloze', body_md: '两种方法是 {{c1::主动回忆::第一种}} 和 {{c2::间隔重复::第二种}}。' })
  const group = await (await request.get(base + '/api/collections/' + collectionId)).json()
  await api(request, '/collections/' + collectionId + '/items', { expected_revision: group.revision, card_ids: [cloze.id] })
  const directory = await (await request.get(base + '/api/collections/' + collectionId + '/items')).json()
  const item = directory.items.find((c: { id: string }) => c.id === cloze.id).item_id
  const before = await (await request.get(base + '/api/reviews/summary')).json()
  await page.goto('/collections/' + collectionId + '?view=read&item=' + item)
  await expect(page.locator('.reader-content')).toContainText('【第一种】')
  await expect(page.locator('.reader-content')).not.toContainText('间隔重复')
  await page.getByRole('button', { name: '显示答案' }).click()
  await expect(page.locator('.reader-content')).toContainText('主动回忆 和 间隔重复')
  await page.getByRole('button', { name: '＋ 添加卡片' }).click()
  const input = page.getByRole('textbox', { name: '搜索要关联的卡片' }); await input.fill('保留输入')
  const url = page.url(); await input.press('ArrowLeft'); expect(page.url()).toBe(url)
  await page.getByRole('button', { name: '＋ 添加卡片' }).click()
  await page.getByRole('combobox', { name: '翻阅顺序' }).selectOption('random')
  const first = await page.locator('.reader-card h2').textContent()
  // Move to the beginning, then traverse the same random sequence twice.
  while (await page.getByRole('button', { name: '← 上一张' }).isEnabled()) await page.getByRole('button', { name: '← 上一张' }).click()
  const titles: string[] = [await page.locator('.reader-card h2').textContent() || '']
  while (await page.getByRole('button', { name: '下一张 →' }).isEnabled()) { await page.getByRole('button', { name: '下一张 →' }).click(); titles.push(await page.locator('.reader-card h2').textContent() || '') }
  for (let n = titles.length - 2; n >= 0; n--) { await page.getByRole('button', { name: '← 上一张' }).click(); await expect(page.locator('.reader-card h2')).toHaveText(titles[n]) }
  expect(new Set(titles).size).toBe(3); expect(titles).toContain(first)
  const after = await (await request.get(base + '/api/reviews/summary')).json()
  expect(after.today_completed).toBe(before.today_completed)
})
