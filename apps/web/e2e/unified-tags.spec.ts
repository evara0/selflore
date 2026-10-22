import { test, expect, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const base = 'http://127.0.0.1:24568'
const shots = path.resolve('../../.cache/frontend-visual-review/unify-card-tags/current')
async function login(page: Page) {
  if (process.env.SELFLORE_TEST_ISOLATED !== '1')
    throw new Error('Task-owned disposable service required')
  const data = {
    username: 'tags_' + randomUUID().slice(0, 8),
    password: 'isolated-tag-password-123',
  }
  for (const action of ['register', 'login'])
    expect(
      (
        await page.request.post(base + '/api/auth/' + action, { data, headers: { Origin: base } })
      ).ok(),
    ).toBeTruthy()
}
async function api(page: Page, url: string, data: object, method = 'POST') {
  const token = (await (await page.request.get(base + '/api/auth/me')).json()).csrf_token
  const response = await page.request.fetch(base + '/api' + url, {
    method,
    data,
    headers: { Origin: base, 'X-CSRF-Token': token },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.status() === 204 ? undefined : response.json()
}
async function create(
  page: Page,
  kind: string,
  title: string,
  tag_ids: string[],
  extra: object = {},
) {
  return api(page, '/cards', {
    kind,
    title,
    client_request_id: randomUUID(),
    taxonomy_mode: 'unified',
    tag_ids,
    ...(kind === 'knowledge'
      ? { form: 'qa', question_md: '如何理解这个概念？', answer_md: '先明确来源，再主动回忆。' }
      : kind === 'memo'
        ? { memo_format: 'note' }
        : { body_md: '保留原材料，并用标签在之后整理。' }),
    ...extra,
  })
}

test('four editors persist shared tags, empty capture, old URLs and mixed clients', async ({
  page,
}) => {
  test.setTimeout(120000)
  await login(page)
  const ai = await api(page, '/tags', { name: '人工智能' }),
    llm = await api(page, '/tags', { name: 'LLM' })
  const saved = []
  for (const kind of ['knowledge', 'reference', 'opinion', 'memo']) {
    await page.goto('/new?kind=' + kind)
    await page.getByLabel('标题', { exact: true }).fill('统一标签-' + kind)
    if (kind === 'knowledge') {
      await page.getByLabel('问题', { exact: true }).fill('问题')
      await page.getByLabel('答案', { exact: true }).fill('答案')
    }
    if (kind === 'reference') await page.getByLabel('原始摘录', { exact: true }).fill('原始材料')
    if (kind === 'opinion') await page.getByLabel('观点正文', { exact: true }).fill('独立观点')
    if (kind === 'memo') await page.getByText('标签与来源（可选）', { exact: true }).click()
    const input = page.getByRole('textbox', { name: '搜索标签' })
    await input.fill('人工智能')
    await input.press('Enter')
    await expect(page.getByRole('button', { name: '移除 人工智能' })).toBeVisible()
    await input.fill('LLM')
    await page.locator('.tag-options button').filter({ hasText: 'LLM' }).tap()
    await page
      .getByRole('button', { name: kind === 'memo' ? '保存备忘' : '保存卡片', exact: true })
      .click()
    await expect(page).toHaveURL(
      new RegExp('/' + (kind === 'memo' ? 'memos' : 'cards') + '/[a-f0-9-]+$'),
    )
    saved.push(page.url().split('/').pop()!)
    await page.reload()
    await expect(page.locator('.card-detail .tags')).toContainText('人工智能')
    const card = await (await page.request.get(base + '/api/cards/' + saved.at(-1))).json()
    expect(new Set(card.tag_ids)).toEqual(new Set([ai.id, llm.id]))
  }
  const empty = await create(page, 'reference', '先收录后整理', [])
  await page.goto('/cards/' + empty.id + '/edit')
  await expect(page.getByText('可稍后整理')).toBeVisible()
  const topic = await api(page, '/topics', { kind: 'knowledge', name: '人工智能' })
  await page.goto('/knowledge?topic=' + topic.id + '&tag=' + llm.id + '&q=统一标签')
  await expect(page.locator('.section-title')).toContainText('1 张卡片')
  await expect(page.getByText('统一标签-reference', { exact: true })).toHaveCount(0)
  let card = await (await page.request.get(base + '/api/cards/' + saved[0])).json()
  card = await api(
    page,
    '/cards/' + card.id,
    { expected_revision: card.revision, topic_ids: [] },
    'PATCH',
  )
  expect(new Set(card.tag_ids)).toEqual(new Set([ai.id, llm.id]))
  await page.goto('/cards?type=all&tag_ids=' + ai.id + '&tag_ids=' + llm.id)
  await expect(page.locator('.section-title')).toContainText('3 张卡片')
  await page.getByLabel('标签匹配方式').selectOption('any')
  await expect(page).toHaveURL(/tag_match=any/)
  await page.reload()
  await expect(page.getByLabel('标签匹配方式')).toHaveValue('any')
  await page.getByRole('button', { name: '清空标签筛选' }).click()
  await expect(page.locator('.section-title')).toContainText('4 张卡片')
  await page.goBack()
  await expect(page.getByLabel('标签匹配方式')).toHaveValue('any')
  await page.goto('/settings')
  const management = page.locator('.tag-management')
  await management.getByRole('textbox', { name: '新标签名称' }).fill('管理测试')
  await management.getByRole('button', { name: '新建标签', exact: true }).click()
  const row = management.locator('.directory-row').filter({ hasText: '管理测试' })
  await expect(row).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept('改名后的标签'))
  await row.getByRole('button', { name: '重命名' }).click()
  const renamed = management.locator('.directory-row').filter({ hasText: '改名后的标签' })
  await expect(renamed).toBeVisible()
  await renamed.getByRole('button', { name: '删除', exact: true }).click()
  await expect(renamed).toHaveCount(0)
  await management
    .locator('.directory-row')
    .filter({ hasText: '人工智能' })
    .getByRole('button', { name: '删除', exact: true })
    .click()
  await expect(management.getByRole('status')).toContainText('仍被卡片使用')
})

test('current build visual matrix and selector failure states', async ({ page }) => {
  test.setTimeout(240000)
  page.setDefaultTimeout(10000)
  await login(page)
  await mkdir(shots, { recursive: true })
  const labels = []
  for (const name of [
    '人工智能',
    'LLM',
    '信息图',
    '长标签'.repeat(26) + '长名',
    ...Array.from({ length: 27 }, (_, i) => '整理主题' + i),
  ])
    labels.push(await api(page, '/tags', { name }))
  const ids = labels.slice(0, 3).map((t) => t.id),
    long = labels[3].id
  const knowledge = await create(page, 'knowledge', '事实知识：主动回忆', ids)
  const reference = await create(page, 'reference', '资料：带有完整来源的摘录', [...ids, long], {
    source_author: '测试作者',
    note_md: '个人说明与原文分开。',
  })
  const opinion = await create(
    page,
    'opinion',
    '观点：连接比收藏更重要',
    labels.slice(0, 30).map((t) => t.id),
  )
  const memo = await create(page, 'memo', '备忘：稍后整理', [])
  const checklist = await create(page, 'memo', '待学清单', ids, {
    memo_format: 'checklist',
    memo_items: [
      { id: randomUUID(), text: '核实资料中的数字' },
      { id: randomUUID(), text: '完成资料阅读', is_completed: true },
    ],
  })
  const collection = await api(page, '/collections', {
    title: '按顺序阅读',
    client_request_id: randomUUID(),
  })
  await api(page, '/collections/' + collection.id + '/items', {
    expected_revision: collection.revision,
    card_ids: [reference.id, knowledge.id, opinion.id],
  })
  const cases = [
    ['cards-all', '/cards?type=all'],
    ['cards-knowledge', '/cards?type=knowledge'],
    ['cards-reference', '/cards?type=reference'],
    ['cards-opinion', '/cards?type=opinion'],
    ['memos-all', '/memos'],
    ['memos-note', '/memos?view=note'],
    ['memos-checklist', '/memos?view=checklist'],
    ['memos-open', '/memos?view=open&tag_ids=' + ids[0]],
    ['review', '/knowledge/review?tag_ids=' + ids[0]],
    ['collections', '/collections'],
    ['collection-reader', '/collections/' + collection.id],
    ['me', '/me'],
    ['settings-tags', '/settings'],
    ['filter-unavailable', '/cards?type=all&tag_ids=' + randomUUID()],
    ['detail-knowledge', '/cards/' + knowledge.id],
    ['detail-reference', '/cards/' + reference.id],
    ['detail-opinion', '/cards/' + opinion.id],
    ['detail-checklist', '/memos/' + checklist.id],
    ['edit-knowledge', '/cards/' + knowledge.id + '/edit'],
    ['edit-reference', '/cards/' + reference.id + '/edit'],
    ['edit-opinion-30', '/cards/' + opinion.id + '/edit'],
    ['edit-memo-empty', '/memos/' + memo.id + '/edit'],
    [
      'filter-multiple',
      '/cards?type=all&tag_ids=' + ids[0] + '&tag_ids=' + long + '&tag_match=any',
    ],
  ]
  const evidence: {
    name: string
    width: number
    file: string
    height: number
    viewport_files?: { file: string; y: number }[]
  }[] = []
  const only = process.env.SELFLORE_VISUAL_ONLY?.split(',')
  const selectedCase = (name: string) => !only || only.some((prefix) => name.startsWith(prefix))
  async function capture(name: string, width: number, loading = false) {
    if (!loading) {
      await page.waitForLoadState('networkidle')
      await expect(page.getByText('正在加载…', { exact: true })).toHaveCount(0)
    }
    await page.evaluate(async () => {
      window.scrollTo(0, 0)
      await new Promise(requestAnimationFrame)
      await new Promise(requestAnimationFrame)
    })
    await expect(page.locator('header.topbar')).toBeInViewport()
    await page.screenshot({ path: path.join(shots, `${name}-${width}.png`), fullPage: true })
    const height = await page.locator('body').evaluate((el) => el.scrollHeight)
    const viewport_files: { file: string; y: number }[] = []
    if (only) {
      let position = 0
      while (true) {
        await page.evaluate(async (y) => {
          window.scrollTo(0, y)
          await new Promise(requestAnimationFrame)
          await new Promise(requestAnimationFrame)
        }, position)
        const actualY = await page.evaluate(() => window.scrollY)
        const file = `${name}-${width}-viewport-${viewport_files.length}.png`
        await page.screenshot({ path: path.join(shots, file) })
        viewport_files.push({ file, y: actualY })
        if (actualY + 900 >= height) break
        position = actualY + 700
      }
    }
    evidence.push({
      name,
      width,
      file: `${name}-${width}.png`,
      height,
      ...(viewport_files.length ? { viewport_files } : {}),
    })
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.screenshot({ path: path.join(shots, `${name}-${width}-end.png`) })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
  }
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    let releaseTags!: () => void
    const gate = new Promise<void>((resolve) => {
      releaseTags = resolve
    })
    await page.route('**/api/tags', async (route) => {
      await gate
      await route.continue()
    })
    await page.goto('/new?kind=reference')
    await expect(page.getByRole('textbox', { name: '搜索标签' })).toBeVisible()
    await expect(page.getByText('正在加载…', { exact: true })).toBeVisible()
    await capture('selector-loading', width, true)
    releaseTags()
    await page.waitForLoadState('networkidle')
    await page.unroute('**/api/tags')
    for (const [name, url] of cases) {
      if (!selectedCase(name)) continue
      await page.goto(url)
      await expect(page.locator('main')).toBeVisible()
      await expect(page.getByText('正在加载页面…', { exact: true })).toHaveCount(0)
      if (name.startsWith('edit-')) {
        await expect(page.getByLabel('标题', { exact: true })).toBeVisible()
        if (name === 'edit-memo-empty')
          await page.getByText('标签与来源（可选）', { exact: true }).click()
        await expect(page.getByRole('textbox', { name: '搜索标签' })).toBeVisible()
      } else if (name.startsWith('detail-'))
        await expect(page.locator('.card-detail')).toBeVisible()
      else await expect(page.getByText('加载中…', { exact: true })).toHaveCount(0)
      await capture(name, width)
    }
    await page.goto('/settings')
    await page
      .locator('.tag-management .directory-row')
      .filter({ hasText: '人工智能' })
      .getByRole('button', { name: '删除', exact: true })
      .click()
    await expect(page.locator('.tag-management').getByRole('status')).toContainText('仍被卡片使用')
    await capture('settings-tag-in-use', width)
    await page.goto('/new?kind=reference')
    await page.getByLabel('标题', { exact: true }).fill('保留编辑输入')
    const input = page.getByRole('textbox', { name: '搜索标签' })
    await input.fill('整理主题')
    for (let i = 0; i < 18; i++) await input.press('ArrowDown')
    await expect(page.locator('.keyboard-active')).toBeInViewport()
    await capture('selector-keyboard-scroll', width)
    await input.fill('待创建标签')
    await page.route('**/api/tags', (route) =>
      route.request().method() === 'POST'
        ? route.fulfill({
            status: 503,
            contentType: 'application/json',
            body: JSON.stringify({ detail: { message: '创建失败，请重试' } }),
          })
        : route.continue(),
    )
    await page.getByRole('button', { name: '新建标签' }).tap()
    await expect(page.getByText('创建失败，请重试', { exact: true })).toBeVisible()
    await capture('selector-create-error', width)
    await page.unroute('**/api/tags')
    await input.fill('ＡＩ')
    await page.getByRole('button', { name: '新建标签' }).click()
    await expect(page.getByRole('button', { name: '移除 AI', exact: true })).toBeVisible()
    // NFKC duplicate response selects the existing canonical label.
    await input.fill('ＡＩ')
    await page.getByRole('button', { name: '新建标签' }).click()
    await expect(page.getByText('已选用同名标签', { exact: true })).toBeVisible()
    await capture('selector-duplicate', width)
    await input.fill('LLM')
    await input.press('ArrowDown')
    await input.press('Enter')
    await input.press('Escape')
    await expect(page.locator('.tag-options')).toHaveCount(0)
    await capture('selector-keyboard-closed', width)
    page.once('dialog', (dialog) => dialog.accept())
    await page.goto('/cards/' + reference.id + '/edit')
    await page.getByLabel('标题', { exact: true }).fill('冲突后保留标题')
    await page.route('**/api/cards/' + reference.id, (route) =>
      route.request().method() === 'PATCH'
        ? route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({ detail: { message: '内容已更新，请核对后保存' } }),
          })
        : route.continue(),
    )
    await page.getByRole('button', { name: '保存卡片', exact: true }).click()
    await expect(page.getByText('内容已更新，请核对后保存', { exact: true })).toBeVisible()
    await capture('editor-conflict', width)
    await page.unroute('**/api/cards/' + reference.id)
    page.once('dialog', (dialog) => dialog.accept())
  }
  const oldManifest = only
    ? JSON.parse(await readFile(path.join(shots, 'manifest.json'), 'utf8'))
    : { cases: [] }
  const retained = oldManifest.cases.map(
    (old: { name: string; width: number }) =>
      evidence.find((c) => c.name === old.name && c.width === old.width) || old,
  )
  const additional = evidence.filter(
    (c) =>
      !oldManifest.cases.some(
        (old: { name: string; width: number }) => old.name === c.name && old.width === c.width,
      ),
  )
  await writeFile(
    path.join(shots, 'manifest.json'),
    JSON.stringify({ base, cases: [...retained, ...additional] }, null, 2),
  )
})

test('mixed old and new URL filters fail visibly and can be cleared', async ({ page }) => {
  await login(page)
  const label = await api(page, '/tags', { name: '混合筛选验收' })
  const topic = await api(page, '/topics', { kind: 'knowledge', name: '混合筛选验收' })
  await create(page, 'knowledge', '不应被放宽的结果', [label.id])
  const manifestFile = path.join(shots, 'manifest.json')
  const manifest = JSON.parse(await readFile(manifestFile, 'utf8'))
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`/cards?type=all&topic=${topic.id}&tag_ids=${label.id}`)
    await expect(page.getByRole('alert')).toContainText('不能混用新旧标签筛选')
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: path.join(shots, `filter-mixed-${width}.png`), fullPage: true })
    const height = await page.locator('body').evaluate((el) => el.scrollHeight)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.screenshot({ path: path.join(shots, `filter-mixed-${width}-end.png`) })
    manifest.cases = manifest.cases.filter(
      (c: { name: string; width: number }) => !(c.name === 'filter-mixed' && c.width === width),
    )
    manifest.cases.push({ name: 'filter-mixed', width, file: `filter-mixed-${width}.png`, height })
    await page.getByRole('button', { name: '清空标签筛选' }).click()
    await expect(page.locator('.section-title')).toContainText('1 张卡片')
  }
  await writeFile(manifestFile, JSON.stringify(manifest, null, 2))
})
