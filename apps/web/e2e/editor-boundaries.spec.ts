import { expect, test, type Page } from '@playwright/test'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card, Collection } from '../src/lib/workspace'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

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
        json: {
          is_available: true,
          max_bytes: 10485760,
          max_pixels: 40000000,
          max_edge: 20000,
          max_images: 10,
          formats: ['image/png'],
        },
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

for (const width of [320, 390, 1280]) {
  test(`quick capture preserves manual fields, handles fallback and saves at ${width}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const writes = await fixture(page)
    let fail = false
    let finish: (() => void) | undefined
    await page.route('**/api/sources/resolve', async (route) => {
      if (fail) return route.fulfill({ status: 503, json: { detail: '合成获取失败' } })
      await new Promise<void>((resolve) => {
        finish = resolve
      })
      return route.fulfill({
        json: {
          category: 'x',
          method: 'webpage',
          status: 'partial',
          fallback_reason: 'timeout',
          fields: {
            source_title: '合成资料标题',
            source_author: '建议作者',
            source_platform: 'X',
            source_published_on: '2026-10-19',
          },
        },
      })
    })
    const folder = process.env.SELFLORE_CAPTURE_DIR || testInfo.outputPath('visual')
    await mkdir(folder, { recursive: true })
    const capture = async (name: string) => {
      await page.evaluate(() => document.fonts.ready)
      await expect(page.getByRole('region', { name: '资料卡快速收录' })).toBeVisible()
      await page.getByRole('region', { name: '资料卡快速收录' }).scrollIntoViewIfNeeded()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      expect(
        await page.getByRole('region', { name: '资料卡快速收录' }).evaluate((section) => {
          const bounds = section.getBoundingClientRect()
          return [...section.querySelectorAll('input,select,button')].every((control) => {
            const box = control.getBoundingClientRect()
            return box.left >= bounds.left && box.right <= bounds.right
          })
        }),
      ).toBe(true)
      await page.screenshot({ path: path.join(folder, `capture-${width}-${name}.png`) })
    }
    await page.goto('/new?kind=reference')
    await page.getByLabel('收录链接', { exact: true }).fill('https://x.com/example/status/123')
    await page.getByLabel('标题', { exact: true }).fill('保留我的标题')
    await page.getByLabel('原始摘录', { exact: true }).fill('合成摘录，不写入业务库。')
    await capture('ready')
    await page.getByRole('button', { name: '获取来源信息', exact: true }).click()
    await expect.poll(() => !!finish).toBe(true)
    await page.getByLabel('来源作者', { exact: true }).fill('请求中手改作者')
    finish!()
    await expect(page.getByRole('region', { name: '资料卡快速收录' })).toContainText(
      '已回退普通网页',
    )
    await expect(page.getByLabel('标题', { exact: true })).toHaveValue('保留我的标题')
    await expect(page.getByLabel('来源作者', { exact: true })).toHaveValue('请求中手改作者')
    await expect(page.getByLabel('来源标题', { exact: true })).toHaveValue('合成资料标题')
    await expect(page.getByLabel('来源平台', { exact: true })).toHaveValue('X')
    await capture('fallback')
    fail = true
    await page.getByLabel('获取方式', { exact: true }).selectOption('webpage')
    await page.getByRole('button', { name: '获取来源信息', exact: true }).click()
    await expect(page.getByRole('region', { name: '资料卡快速收录' })).toContainText(
      '暂时无法获取来源',
    )
    await capture('error')
    await page.getByLabel('收录链接').focus()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('获取方式')).toBeFocused()
    const save = page.getByRole('button', { name: '保存卡片', exact: true })
    await save.scrollIntoViewIfNeeded()
    await expect(save).toBeInViewport()
    await save.click()
    await expect(page.getByRole('status').filter({ hasText: '合成临时错误' })).toBeVisible()
    await save.click()
    await expect(page.getByRole('heading', { name: '保留我的标题', exact: true })).toBeVisible()
    expect(writes.filter((write) => write.path === '/cards').at(-1)?.body).toMatchObject({
      source_url: 'https://x.com/example/status/123',
      source_author: '请求中手改作者',
      source_title: '合成资料标题',
      source_platform: 'X',
      source_published_on: '2026-10-19',
      body_md: '合成摘录，不写入业务库。',
      attachments: [],
    })
  })
}

test('ordinary knowledge editor does not show quick capture', async ({ page }) => {
  await fixture(page)
  await page.goto('/new?kind=knowledge')
  await expect(page.getByLabel('问题', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '资料卡快速收录' })).toHaveCount(0)
})

for (const width of [320, 390, 1280]) {
  test(`blank card type choices leave for memo without confirmation at ${width}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 844 })
    const writes = await fixture(page)
    const dialogs: string[] = []
    page.on('dialog', async (dialog) => {
      dialogs.push(dialog.message())
      await dialog.dismiss()
    })
    const folder = process.env.SELFLORE_CAPTURE_DIR || testInfo.outputPath('visual')
    await mkdir(folder, { recursive: true })
    for (const kind of ['knowledge', 'opinion', 'reference']) {
      await page.goto('/new?kind=' + kind)
      for (const name of ['事实知识', '观点', '资料卡']) {
        const tab = page.getByRole('button', { name, exact: true })
        await tab.click()
        await tab.click()
      }
      await expect(page.getByLabel('标题', { exact: true })).toHaveValue('')
      await page.evaluate(() => document.fonts.ready)
      if (kind === 'knowledge')
        await page.screenshot({ path: path.join(folder, `new-card-${width}-blank.png`) })
      const memo = page.getByRole('link', { name: '备忘 / 清单', exact: true })
      await memo.focus()
      await page.keyboard.press('Enter')
      await expect(page.getByRole('heading', { name: '新建备忘', exact: true })).toBeVisible()
      await expect(page).toHaveURL(/kind=memo/)
      if (kind === 'knowledge') {
        await page.evaluate(() => document.fonts.ready)
        await page.screenshot({ path: path.join(folder, `new-memo-${width}-blank.png`) })
        await page
          .getByRole('button', { name: '保存备忘', exact: true })
          .evaluate((button) => button.scrollIntoView({ block: 'center', behavior: 'instant' }))
        await expect(page.getByRole('button', { name: '保存备忘', exact: true })).toBeInViewport()
        await page.screenshot({ path: path.join(folder, `new-memo-${width}-footer.png`) })
      }
    }
    expect(dialogs).toEqual([])
    expect(writes).toEqual([])
  })
}

for (const field of ['标题', '问题', '来源作者']) {
  test(`card type choices retain unsaved protection for ${field}`, async ({ page }) => {
    const writes = await fixture(page)
    await page.goto('/new?kind=knowledge')
    await page.getByRole('textbox', { name: field, exact: true }).fill('保留的输入')
    await page.getByRole('button', { name: '观点', exact: true }).click()
    await page.getByRole('button', { name: '资料卡', exact: true }).click()
    let confirmation = ''
    page.once('dialog', async (dialog) => {
      confirmation = dialog.message()
      await dialog.dismiss()
    })
    await page.getByRole('link', { name: '备忘 / 清单', exact: true }).click()
    await expect.poll(() => confirmation).toBe('内容尚未保存，确定离开？')
    await expect(page.getByRole('heading', { name: '新建卡片', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '事实知识', exact: true }).click()
    await expect(page.getByRole('textbox', { name: field, exact: true })).toHaveValue('保留的输入')
    page.once('dialog', async (dialog) => {
      await dialog.accept()
    })
    await page.getByRole('link', { name: '备忘 / 清单', exact: true }).click()
    await expect(page.getByRole('heading', { name: '新建备忘', exact: true })).toBeVisible()
    expect(writes).toEqual([])
  })
}

test('capture fills a blank title but preserves fields cleared during the request', async ({
  page,
}) => {
  await fixture(page)
  let finish: (() => void) | undefined
  await page.route('**/api/sources/resolve', async (route) => {
    await new Promise<void>((resolve) => {
      finish = resolve
    })
    return route.fulfill({
      json: {
        category: 'webpage',
        method: 'webpage',
        status: 'success',
        fallback_reason: null,
        fields: {
          source_title: '网页标题',
          source_author: '作者建议',
          source_platform: '站点',
          source_publisher: '明确发布者',
        },
      },
    })
  })
  await page.goto('/new?kind=reference')
  await page.getByLabel('收录链接').fill('https://example.com/article')
  await page.getByLabel('来源作者', { exact: true }).fill('待清空')
  await page.getByRole('button', { name: '获取来源信息', exact: true }).click()
  await expect.poll(() => !!finish).toBe(true)
  await page.getByLabel('来源作者', { exact: true }).fill('')
  finish!()
  await expect(page.getByLabel('标题', { exact: true })).toHaveValue('网页标题')
  await expect(page.getByLabel('来源作者', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('发布／转载者', { exact: true })).toHaveValue('明确发布者')
})

test('existing reference retains its content when source lookup has no metadata', async ({
  page,
}, testInfo) => {
  await fixture(page)
  await page.setViewportSize({ width: 390, height: 900 })
  await page.route('**/api/sources/resolve', (route) =>
    route.fulfill({
      json: {
        category: 'webpage',
        method: 'webpage',
        status: 'unavailable',
        fallback_reason: null,
        fields: {},
      },
    }),
  )
  await page.goto('/cards/' + demoId(10) + '/edit')
  await expect(page.getByRole('heading', { name: '编辑卡片', exact: true })).toBeVisible()
  const originalTitle = await page.getByLabel('标题', { exact: true }).inputValue()
  const originalExcerpt = await page
    .getByRole('textbox', { name: '原始摘录', exact: true })
    .inputValue()
  await page.getByLabel('收录链接').fill('https://example.com/existing')
  await page.getByRole('button', { name: '获取来源信息', exact: true }).click()
  await expect(page.getByRole('region', { name: '资料卡快速收录' })).toContainText(
    '未获取到可用信息',
  )
  await expect(page.getByLabel('标题', { exact: true })).toHaveValue(originalTitle)
  await expect(page.getByRole('textbox', { name: '原始摘录', exact: true })).toHaveValue(
    originalExcerpt,
  )
  const folder = process.env.SELFLORE_CAPTURE_DIR || testInfo.outputPath('visual')
  await mkdir(folder, { recursive: true })
  await page.getByRole('region', { name: '资料卡快速收录' }).scrollIntoViewIfNeeded()
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: path.join(folder, 'existing-390-unavailable.png') })
})
