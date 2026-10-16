import { expect, test, type Page } from '@playwright/test'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card, Collection } from '../src/lib/workspace'

const user = {
  id: demoId(900),
  username: 'fixture_user',
  role: 'member',
  is_active: true,
  csrf_token: 'synthetic',
}

// All writes stay in this browser test's memory; no application or database server is used.
async function fixture(page: Page, initiallyLoggedIn = true) {
  let loggedIn = initiallyLoggedIn
  const writes: { path: string; body: Record<string, unknown> }[] = []
  let card: Card | undefined
  let collection: Collection | undefined
  let failCardOnce = true
  await page.route('**/api/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.slice(4)
    if (request.method() !== 'GET') {
      const body = (request.postData() ? request.postDataJSON() : {}) as Record<string, unknown>
      writes.push({ path, body })
      if (path === '/auth/register') return route.fulfill({ status: 201, json: user })
      if (path === '/auth/login') {
        loggedIn = true
        return route.fulfill({ json: user })
      }
      if (path === '/auth/logout') {
        loggedIn = false
        return route.fulfill({ status: 204 })
      }
      if (path === '/cards') {
        if (failCardOnce) {
          failCardOnce = false
          return route.fulfill({ status: 503, json: { detail: '合成临时错误' } })
        }
        card = {
          ...body,
          id: demoId(901),
          code: '示例-901',
          revision: 1,
          lifecycle: 'active',
          tags: [],
          topics: [],
        } as Card
        return route.fulfill({ status: 201, json: card })
      }
      if (path === '/collections') {
        collection = {
          ...body,
          id: demoId(902),
          revision: 1,
          lifecycle: 'active',
          total_items: 0,
          available_items: 0,
        } as Collection
        return route.fulfill({ status: 201, json: collection })
      }
      throw new Error('Unexpected fixture write: ' + path)
    }
    if (path === '/auth/me')
      return route.fulfill(
        loggedIn ? { json: user } : { status: 401, json: { detail: '请先登录' } },
      )
    if (path === '/auth/config') return route.fulfill({ json: { registration_enabled: true } })
    if (path === '/attachments/config')
      return route.fulfill({
        json: { is_available: true, max_bytes: 10485760, max_images: 10, formats: ['image/png'] },
      })
    if (/^\/attachments\/[^/]+\/content$/.test(path))
      return route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="#ddd"/></svg>',
      })
    if (card && path === '/cards/' + card.id) return route.fulfill({ json: card })
    if (path.endsWith('/links')) return route.fulfill({ json: { incoming: [], outgoing: [] } })
    if (collection && path === '/collections/' + collection.id)
      return route.fulfill({ json: collection })
    if (collection && path === '/collections/' + collection.id + '/items')
      return route.fulfill({ json: { revision: 1, items: [] } })
    const url = new URL(request.url())
    try {
      return route.fulfill({ json: readDemo(path + url.search) })
    } catch (error) {
      throw new Error(path + url.search + ': ' + (error as Error).message)
    }
  })
  return writes
}

test('registration, login and logout survive the authentication dialog boundary', async ({
  page,
}) => {
  const writes = await fixture(page, false)
  await page.goto('/cards?type=all')
  await page.getByRole('button', { name: '登录 / 注册', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('tab', { name: '注册', exact: true }).click()
  await dialog.getByLabel('用户名', { exact: true }).fill('fixture_user')
  await dialog.getByLabel('密码', { exact: true }).fill('synthetic-password')
  await dialog.getByLabel('确认密码', { exact: true }).fill('synthetic-password')
  await dialog.getByRole('button', { name: '注册', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('注册成功')
  await dialog.getByLabel('密码', { exact: true }).fill('synthetic-password')
  await dialog.getByRole('button', { name: '登录', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('heading', { name: '卡片', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/type=all/)
  await page.getByRole('button', { name: /fixture_user/ }).click()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '登录 / 注册', exact: true })).toBeVisible()
  expect(writes.map((write) => write.path)).toEqual([
    '/auth/register',
    '/auth/login',
    '/auth/logout',
  ])
})

test('reference source fields and retry identity survive the card form boundary', async ({
  page,
}) => {
  const writes = await fixture(page)
  await page.goto('/new?kind=reference')
  await page.getByLabel('标题', { exact: true }).fill('合成来源测试')
  await page.getByLabel('原始摘录', { exact: true }).fill('仅用于回归的摘录')
  await page.getByLabel('我的说明', { exact: true }).fill('收录说明')
  for (const [label, value] of [
    ['来源标题', '合成材料'],
    ['来源链接', 'https://example.com/material'],
    ['页码 / 定位', '第3段'],
    ['来源作者', '示例作者'],
    ['发布／转载者', '示例发布者'],
    ['来源平台', '示例平台'],
    ['发布日期', '2026-10-16'],
  ])
    await page.getByLabel(label, { exact: true }).fill(value)
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '合成临时错误' })).toBeVisible()
  await expect(page.getByLabel('来源作者', { exact: true })).toHaveValue('示例作者')
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page.getByRole('heading', { name: '合成来源测试', exact: true })).toBeVisible()
  const requests = writes.filter((write) => write.path === '/cards')
  expect(requests).toHaveLength(2)
  expect(requests[0].body).toEqual(requests[1].body)
  expect(requests[1].body).toMatchObject({
    kind: 'reference',
    title: '合成来源测试',
    source_title: '合成材料',
    source_url: 'https://example.com/material',
    source_locator: '第3段',
    source_author: '示例作者',
    source_publisher: '示例发布者',
    source_platform: '示例平台',
    source_published_on: '2026-10-16',
    note_md: '收录说明',
  })
})

test('collection creation keeps its own route and save fields', async ({ page }) => {
  const writes = await fixture(page)
  await page.goto('/collections/new')
  await page.getByLabel('合集名称', { exact: true }).fill('合成合集')
  await page.getByLabel('合集描述', { exact: true }).fill('示例描述')
  await page.getByRole('combobox').nth(0).selectOption('lines')
  await page.getByRole('combobox').nth(1).selectOption('clay')
  await page.getByRole('button', { name: '保存合集', exact: true }).click()
  await expect(page).toHaveURL(new RegExp('/collections/' + demoId(902)))
  await expect(page.getByRole('heading', { name: '合成合集', exact: true })).toBeVisible()
  expect(writes[0].body).toMatchObject({
    title: '合成合集',
    description_md: '示例描述',
    cover_style: 'lines',
    cover_color: 'clay',
  })
})
