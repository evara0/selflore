import { test, expect, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir } from 'node:fs/promises'

const base = 'http://127.0.0.1:24568', password = 'memo-browser-password-123'
async function login(page: Page) {
  if (process.env.SELFLORE_TEST_ISOLATED !== '1') throw new Error('Disposable test service only')
  const username = 'memo_' + randomUUID().slice(0,8)
  for (const path of ['register','login']) {
    const response = await page.request.post(base + '/api/auth/' + path, { data: { username, password }, headers: { Origin: base } })
    expect(response.ok(), await response.text()).toBeTruthy()
  }
  return username
}
async function api(page: Page, path: string, data: object, method = 'POST') {
  const token = (await (await page.request.get(base + '/api/auth/me')).json()).csrf_token
  const response = await page.request.fetch(base + '/api' + path, { method, data, headers: { Origin: base, 'X-CSRF-Token': token } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

test('four navigation, memo capture, checklist, references, pending view, conflicts and recovery', async ({ page }) => {
  test.setTimeout(90000)
  await login(page)
  await page.goto('/memos')
  await expect(page.getByRole('navigation', { name: '主导航' }).getByRole('link')).toHaveText(['卡片','备忘','合集','我的'])
  await page.getByRole('link', { name: '＋ 随手记' }).click()
  await page.getByLabel('标题', { exact: true }).fill('明天查一下图表的依据')
  await page.getByRole('button', { name: '保存备忘' }).click()
  await expect(page).toHaveURL(/\/memos\/[a-f0-9-]+$/)
  await page.reload(); await expect(page.getByRole('heading', { name: '明天查一下图表的依据' })).toBeVisible()
  const target = await api(page, '/cards', { kind: 'knowledge', form: 'qa', title: '待核实的图表', question_md: '图表依据是什么？', answer_md: '合成解释', client_request_id: randomUUID() })
  await page.goto('/new?kind=memo&memo_format=checklist')
  await page.getByLabel('标题', { exact: true }).fill('本周待学计划')
  await page.getByLabel('条目 1', { exact: true }).fill('查找图表数据的原始出处')
  await page.getByRole('button', { name: '关联知识', exact: true }).click()
  await page.getByLabel('搜索要关联的卡片').fill('待核实的图表')
  await page.getByRole('button', { name: /待核实的图表/ }).click()
  await page.getByRole('button', { name: '＋ 添加条目' }).click()
  await page.getByLabel('条目 2', { exact: true }).fill('写下阅读后的疑问')
  await page.getByRole('button', { name: '上移条目 2', exact: true }).click()
  await expect(page.getByLabel('条目 1', { exact: true })).toHaveValue('写下阅读后的疑问')
  await page.getByRole('button', { name: '保存备忘' }).click()
  await expect(page).toHaveURL(/\/memos\/[a-f0-9-]+$/)
  const memoUrl = page.url(), id = memoUrl.split('/').pop()!
  await page.getByRole('checkbox', { name: '写下阅读后的疑问' }).click()
  await expect(page.getByLabel('清单进度')).toHaveText('已完成 1 / 2 项')
  await page.reload(); await expect(page.getByRole('checkbox', { name: '写下阅读后的疑问' })).toBeChecked()
  const completedAt = (await (await page.request.get(base + '/api/cards/' + id)).json()).memo_items[0].completed_at
  await page.goto('/memos?view=open')
  await expect(page.getByText('1 项未完成事项')).toBeVisible()
  await page.getByRole('link', { name: '所属清单：本周待学计划 ↗' }).click()
  await expect(page.locator('.memo-item-highlight')).toContainText('查找图表数据的原始出处')
  await page.goto('/cards/' + target.id)
  await page.getByRole('link', { name: '定位条目 ↗' }).click()
  await expect(page).toHaveURL(/\/memos\/.+\?item=/)
  await page.route('**/api/cards/*/memo-items/*', route => route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: { message: '模拟修订冲突' } }) }))
  await page.getByRole('checkbox', { name: '查找图表数据的原始出处' }).click()
  await expect(page.getByRole('alert')).toContainText('模拟修订冲突')
  await expect(page.getByRole('checkbox', { name: '查找图表数据的原始出处' })).not.toBeChecked()
  await page.unroute('**/api/cards/*/memo-items/*')
  await page.getByRole('link', { name: '编辑卡片 ↗' }).click()
  await page.getByLabel('标题', { exact: true }).fill('本周待学计划（更新）')
  await page.getByRole('button', { name: '保存备忘' }).click()
  await expect(page.getByRole('heading', { name: '本周待学计划（更新）' })).toBeVisible()
  expect((await (await page.request.get(base + '/api/cards/' + id)).json()).memo_items[0].completed_at).toBe(completedAt)
  const group = await api(page, '/collections', { title: '研究主题', client_request_id: randomUUID() })
  await api(page, '/collections/' + group.id + '/items', { expected_revision: 1, card_ids: [id, target.id] })
  await page.goto('/collections/' + group.id + '?view=read')
  await expect(page.getByRole('checkbox').first()).toBeDisabled()
  await page.goto(memoUrl)
  await page.getByRole('button', { name: '移入回收站' }).click()
  await page.goto('/memos?view=open'); await expect(page.getByText('没有未完成事项。')).toBeVisible()
  await page.goto('/trash'); await page.getByRole('button', { name: '恢复', exact: true }).click()
  await page.goto(memoUrl); await expect(page.getByLabel('清单进度')).toHaveText('已完成 1 / 2 项')
  await page.getByRole('checkbox', { name: '写下阅读后的疑问' }).click()
  await expect(page.getByLabel('清单进度')).toHaveText('已完成 0 / 2 项')
  await page.goto('/me'); await expect(page.getByText('备忘卡片', { exact: true })).toBeVisible()
  expect((await (await page.request.get(base + '/api/me/summary')).json()).streak).toBe(1) // Creating the source reference is a learning event; memo actions add none.
})

test('legacy routes, type memory and narrow-screen checklist remain usable', async ({ page }) => {
  test.setTimeout(90000)
  await login(page)
  const source = await api(page, '/cards', { kind: 'opinion', title: '理解后的判断', body_md: '自己的独立观点。', client_request_id: randomUUID() })
  await page.goto('/opinions?card=' + source.id + '&q=理解后的判断')
  await expect(page).toHaveURL(/\/cards\?.*type=opinion/)
  await expect(page.getByRole('heading', { name: '理解后的判断' })).toBeVisible()
  await page.goto('/memos'); await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '卡片', exact: true }).click()
  await expect(page.getByRole('button', { name: '观点', exact: true })).toHaveClass(/selected/)
  await page.goto('/knowledge?type=reference'); await expect(page.getByRole('button', { name: '资料', exact: true })).toHaveClass(/selected/)
  const memo = await api(page, '/cards', { kind: 'memo', memo_format: 'checklist', title: '移动端学习计划', client_request_id: randomUUID(), memo_items: [{ id: randomUUID(), text: '检查很长的条目文字是否正确换行并且仍然可以点击和操作。'.repeat(4) }] })
  await mkdir('../../.cache/memo-browser', { recursive: true })
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 844 }); await page.goto('/memos/' + memo.id)
    await expect(page.getByRole('heading', { name: '移动端学习计划' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (width < 600) {
      const nav = page.getByRole('navigation', { name: '移动端导航' })
      await expect(nav.getByRole('link')).toHaveCount(5)
      const boxes = await nav.getByRole('link').evaluateAll(links => links.map(link => { const b = link.getBoundingClientRect(); return { x: b.x, right: b.right, width: b.width } }))
      expect(boxes.every(b => b.width > 35 && b.x >= 0 && b.right <= width)).toBe(true)
    }
    await page.screenshot({ path: '../../.cache/memo-browser/memo-' + width + '.png', fullPage: true })
  }
})
