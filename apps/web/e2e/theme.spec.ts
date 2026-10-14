import { test, expect, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card } from '../src/lib/workspace'

const shots = '../../docs/design/default-letterpress-theme/implemented'
const cardPath = `/knowledge/cards/${demoId(1)}`
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}
async function shot(page: Page, name: string, fullPage = true) {
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage })
}
async function checkContrast(page: Page) {
  const ratios = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1
    const context = canvas.getContext('2d')!
    function luminance(value: string) {
      context.clearRect(0, 0, 1, 1); context.fillStyle = value; context.fillRect(0, 0, 1, 1)
      return [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0)
    }
    function contrast(a: string, b: string) { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05) }
    const cards = [...document.querySelectorAll('.flashcard')].map(card => {
      const style = getComputedStyle(card), tag = getComputedStyle(card.querySelector('.tag')!)
      return { text: contrast(style.color, style.backgroundColor), tag: contrast(tag.color, tag.backgroundColor) }
    })
    const control = getComputedStyle(document.querySelector('.search-box')!)
    return { cards, boundary: contrast(control.borderColor, control.backgroundColor) }
  })
  for (const result of ratios.cards) { expect(result.text).toBeGreaterThanOrEqual(4.5); expect(result.tag).toBeGreaterThanOrEqual(4.5) }
  expect(ratios.boundary).toBeGreaterThanOrEqual(3)
}

test('letterpress identity survives sorting, detail, collection and guest navigation', async ({ page }) => {
  test.setTimeout(180000)
  await mkdir(shots, { recursive: true })
  const requests: string[] = [], errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    requests.push(`${route.request().method()} ${path}`)
    if (path === '/api/auth/me') await route.fulfill({ status: 401, json: { detail: '请先登录' } })
    else if (path === '/api/auth/config') await route.fulfill({ json: { registration_enabled: true } })
    else await route.abort()
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/knowledge?type=knowledge&sort=code_asc')
  await expect(page.locator('.flashcard')).toHaveCount(6)
  const inks = await page.locator('.flashcard').evaluateAll(elements => Object.fromEntries(elements.map(e => [e.getAttribute('data-card-id'), e.getAttribute('data-card-ink')])))
  expect(new Set(Object.values(inks)).size).toBe(4)
  await checkContrast(page)
  await shot(page, '01-knowledge-desktop')
  await page.getByLabel('知识排序').selectOption('updated_desc')
  await expect(page.locator('.flashcard').first()).toHaveAttribute('data-card-id', demoId(6))
  expect(await page.locator('.flashcard').evaluateAll(elements => Object.fromEntries(elements.map(e => [e.getAttribute('data-card-id'), e.getAttribute('data-card-ink')])))).toEqual(inks)
  await page.getByRole('link', { name: '主动回忆为什么有效？', exact: true }).click()
  const detail = page.locator('.card-detail')
  await expect(detail).toHaveAttribute('data-card-ink', inks[demoId(1)])
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  await expect(detail.locator('.answer')).toBeVisible()
  const ink = await detail.evaluate(e => getComputedStyle(e).color)
  for (const selector of ['h2', '.tag', '.markdown', '.card-code']) {
    expect(await detail.locator(selector).first().evaluate(e => getComputedStyle(e).color)).toBe(ink)
  }
  await shot(page, '02-card-detail-answer')
  await page.goto(`/collections/${demoId(301)}?view=read`)
  await expect(page.locator('.reader-card')).toHaveAttribute('data-card-ink', inks[demoId(1)])
  await expect(page.locator('.reader-card')).toHaveCSS('color', ink)
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  await page.getByRole('button', { name: '下一张 →' }).click()
  await expect(page.locator('.reader-card .answer')).toHaveCount(0)
  await expect(page.locator('.reader-card')).toHaveAttribute('data-card-ink', inks[demoId(3)])
  await shot(page, '03-collection-reader')
  for (const [url, name] of [[`/opinions?card=${demoId(7)}`, '04-opinions-desktop'], ['/collections', '05-collections-desktop'], ['/me', '06-profile-desktop']]) {
    await page.goto(url)
    await expect(page.locator('.state[role="status"]')).toHaveCount(0)
    await shot(page, name)
  }
  await expect(page.locator('.heat-cell[title]')).toHaveCount(84)
  const paths = ['/knowledge', `/opinions?card=${demoId(7)}`, '/collections', '/me', cardPath]
  for (const width of [320, 390, 736, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const url of paths) {
      await page.goto(url)
      await expect(page.locator('.state[role="status"]')).toHaveCount(0)
      await noOverflow(page)
    }
  }
  await page.setViewportSize({ width: 390, height: 1100 })
  await page.goto('/knowledge?type=knowledge&sort=code_asc')
  await expect(page.locator('.flashcard')).toHaveCount(6)
  await shot(page, '07-knowledge-mobile', false)
  const nav = page.getByRole('navigation', { name: '移动端导航' })
  await expect(nav.getByRole('link', { name: '新建', exact: true })).toBeVisible()
  await page.locator('.flashcard').first().getByRole('button', { name: /查看答案/ }).tap()
  await expect(page.locator('.flash-answer')).toBeVisible()
  await page.locator('.flashcard').first().getByRole('button', { name: /取消收藏/ }).tap()
  await expect(page.getByRole('dialog')).toBeVisible()
  await shot(page, '08-login-mobile', false)
  await page.getByRole('tab', { name: '注册' }).tap()
  await page.getByLabel('用户名', { exact: true }).fill('bad name')
  await page.getByLabel('密码', { exact: true }).click()
  await expect(page.locator('.auth-error')).toBeVisible()
  await noOverflow(page)
  expect(requests.every(r => r === 'GET /api/auth/me' || r === 'GET /api/auth/config')).toBe(true)
  expect(errors).toEqual([])
})

test('actual auxiliary views, review ink, long content and media stay usable', async ({ page }) => {
  test.setTimeout(180000)
  await mkdir(shots, { recursive: true })
  const baseCard = readDemo<Card>(`/cards/${demoId(1)}`)
  const longCard: Card = { ...baseCard, title: '长标题与卡片的实体边框：让知识和思考慢慢长成自己的样子'.repeat(2),
    source_url: `https://example.com/${'long-source-'.repeat(35)}`,
    tags: [{ id: 'a', name: '主动回忆与思考的长标签'.repeat(3) }, { id: 'b', name: '第二个标签' }],
    question_md: '代码和长链接也应完整可读。\n\n```ts\n'+ 'const longVariable = "'+ 'long-source'.repeat(30) +'"\n```',
  }
  const reference = { ...readDemo<Card>(`/cards/${demoId(10)}`),
    attachments: [0, 1].map(n => ({ id: demoId(500 + n), caption: `彩色资料 ${n + 1}`, alt_text: '蓝橙色完整资料图' })) }
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname.slice(4)
    if (path === '/auth/me') await route.fulfill({ json: { id: demoId(900), username: 'theme_fixture', role: 'admin', is_active: true, csrf_token: 'theme-fixture-only' } })
    else if (path === '/auth/config') await route.fulfill({ json: { registration_enabled: true } })
    else if (path.startsWith('/attachments/')) await route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400"><rect width="320" height="400" fill="#325c83"/><rect x="320" width="320" height="400" fill="#a65d2b"/></svg>' })
    else if (path === `/cards/${demoId(1)}`) await route.fulfill({ json: longCard })
    else if (path === `/cards/${demoId(10)}`) await route.fulfill({ json: reference })
    else if (path === '/reviews/queue') await route.fulfill({ json: { items: [{ id: demoId(800), card: baseCard, question: '什么是主动回忆？', answer: baseCard.answer_md, state: 'new', state_version: 1 }], new_allowance: 20, next_due_at: null } })
    else if (path.endsWith('/preview')) await route.fulfill({ json: { intervals: [60, 300, 86400, 172800].map((seconds, i) => ({ rating: i + 1, seconds })) } })
    else if (path.startsWith('/admin/users')) await route.fulfill({ json: { items: [{ id: demoId(900), username: 'theme_fixture', role: 'admin', is_active: true }], total: 1, limit: 20, offset: 0 } })
    else if (url.searchParams.get('lifecycle') === 'trashed') await route.fulfill({ json: { items: [], total: 0, limit: 20, offset: 0 } })
    else if (route.request().method() !== 'GET') await route.fulfill({ status: 503, json: { detail: '主题验收模拟保存失败，输入已保留。' } })
    else { try { await route.fulfill({ json: readDemo(path + url.search) }) } catch { await route.fulfill({ status: 404, json: { detail: '验收数据不可用' } }) } }
  })
  const views = ['/new', '/collections/new', '/settings', '/admin/users', '/trash', '/knowledge/review', cardPath, `/knowledge/references/${demoId(10)}`]
  for (const width of [320, 390, 736, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const url of views) {
      await page.goto(url)
      await expect(page.locator('.state[role="status"]')).toHaveCount(0)
      await noOverflow(page)
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const [url, name] of [['/new', '09-editor'], ['/settings', '10-settings'], ['/admin/users', '11-admin'], ['/trash', '12-trash'], [cardPath, '13-long-content'], [`/knowledge/references/${demoId(10)}`, '14-reference-color']]) {
    await page.goto(url)
    await expect(page.locator('.state[role="status"]')).toHaveCount(0)
    await shot(page, name)
  }
  const image = page.locator('.attachment-thumb').first()
  await expect(image).toBeVisible()
  await expect(image).toHaveCSS('filter', 'none')
  await page.getByRole('button', { name: '放大图片 彩色资料 1' }).click()
  await expect(page.locator('.original-image')).toBeVisible()
  await noOverflow(page)
  await shot(page, '15-original-image', false)
  await page.keyboard.press('Escape')
  await page.goto('/knowledge/review')
  await page.getByRole('button', { name: '显示答案', exact: true }).click()
  const study = page.locator('.study-card')
  await expect(study).toHaveAttribute('data-card-id', demoId(1))
  await page.getByRole('button', { name: /良好/ }).hover()
  expect(await study.locator('.rating-3').evaluate(e => {
    const s = getComputedStyle(e); return s.color !== s.backgroundColor
  })).toBe(true)
  await shot(page, '16-review-ratings')
  await page.setViewportSize({ width: 390, height: 1000 })
  await shot(page, '17-review-mobile', false)
  await page.goto('/new')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByLabel('标题', { exact: true }).fill('保存失败仍保留的主题验收输入')
  await page.getByLabel('问题', { exact: true }).fill('输入是否保留？')
  await page.getByLabel('答案', { exact: true }).fill('应该保留。')
  await page.getByRole('textbox', { name: '问题', exact: true }).press('Tab')
  await expect(page.getByRole('textbox', { name: '答案', exact: true })).toBeFocused()
  expect(await page.getByRole('textbox', { name: '答案', exact: true }).evaluate(e => getComputedStyle(e).outlineStyle)).not.toBe('none')
  await page.getByRole('button', { name: '保存卡片', exact: true }).click()
  await expect(page.getByText('主题验收模拟保存失败，输入已保留。')).toBeVisible()
  await expect(page.getByLabel('标题', { exact: true })).toHaveValue('保存失败仍保留的主题验收输入')
})
