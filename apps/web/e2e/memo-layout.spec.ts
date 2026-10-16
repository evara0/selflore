import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card } from '../src/lib/workspace'

const shots = '../../.cache/frontend-visual-review/20261016-memo-layout'
for (const width of [320, 390, 600, 601, 1280]) {
  test(`memo cards keep text inside frames and checklist actions stay grouped at ${width}px`, async ({ page }, testInfo) => {
    await mkdir(shots, { recursive: true })
    await page.setViewportSize({ width, height: width === 1280 ? 900 : 844 })
    const title = '待核实图表与待学材料：长标题换行和清单阅读检查'
    const text = '核实原始资料中的数字，记录出处并整理疑问。'.repeat(5)
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.slice(4)
      if (request.method() !== 'GET') throw new Error('Layout fixtures must not write business data')
      if (path === '/auth/me') await route.fulfill({ json: { id: demoId(900), username: 'layout_fixture', role: 'member', csrf_token: 'synthetic-only' } })
      else if (path === '/auth/config') await route.fulfill({ json: { registration_enabled: true } })
      else {
        const value = readDemo(path + url.search)
        if (path === '/cards' && url.searchParams.get('kind') === 'memo') {
          const row = (value as { items: Card[] }).items.find(c => c.id === demoId(12))!
          row.title = title; row.excerpt = 'OriginalSourceWithoutSpaces'.repeat(6)
        } else if (path === '/cards/' + demoId(12)) {
          const card = value as Card
          card.title = title; card.memo_items![1].text = text
        }
        await route.fulfill({ json: value })
      }
    })
    await page.goto('/memos')
    const cards = page.locator('.memo-card')
    await expect(cards).toHaveCount(2)
    const metrics = await cards.evaluateAll(elements => elements.map(element => {
      const box = element.getBoundingClientRect(), style = getComputedStyle(element)
      const childBounds = [...element.children].map(child => { const b = child.getBoundingClientRect(); return { left: b.left - box.left, right: box.right - b.right } })
      return { padding: parseFloat(style.paddingLeft), childBounds }
    }))
    for (const metric of metrics) {
      expect(metric.padding).toBeGreaterThanOrEqual(16)
      expect(metric.childBounds.every(b => b.left >= 16 && b.right >= 16)).toBe(true)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: `${shots}/memos-${width}.png`, fullPage: true })
    await testInfo.attach('card-layout', { body: JSON.stringify(metrics), contentType: 'application/json' })

    await page.getByRole('link', { name: title, exact: true }).click()
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
    await page.getByRole('link', { name: '编辑卡片 ↗' }).click()
    const first = page.locator('.memo-edit-items > li').first()
    await expect(page.getByLabel('条目 2', { exact: true })).toHaveValue(text)
    const groups = await first.locator('.memo-item-actions').evaluate(element => {
      const label = element.querySelector('label')!.getBoundingClientRect()
      const order = element.querySelector('.memo-item-order')!.getBoundingClientRect()
      const tools = element.querySelector('.memo-item-tools')!.getBoundingClientRect()
      const buttons = [...element.querySelectorAll('button')].map(b => { const r = b.getBoundingClientRect(); return { top: r.top, height: r.height, width: r.width, right: r.right } })
      return { labelCenter: label.top + label.height / 2, orderCenter: order.top + order.height / 2, orderBottom: order.bottom, toolsTop: tools.top, buttons }
    })
    expect(Math.abs(groups.labelCenter - groups.orderCenter)).toBeLessThanOrEqual(1)
    expect(groups.buttons.every(b => b.height >= 44)).toBe(true)
    expect(Math.abs(groups.buttons[0].top - groups.buttons[1].top)).toBeLessThanOrEqual(1)
    expect(Math.abs(groups.buttons[2].top - groups.buttons[3].top)).toBeLessThanOrEqual(1)
    if (width <= 600) {
      expect(groups.toolsTop).toBeGreaterThanOrEqual(groups.orderBottom + 7)
      expect(Math.abs(groups.buttons[2].width - groups.buttons[3].width)).toBeLessThanOrEqual(1)
    } else expect(Math.abs(groups.buttons[0].top - groups.buttons[2].top)).toBeLessThanOrEqual(1)
    await testInfo.attach('action-layout', { body: JSON.stringify(groups), contentType: 'application/json' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await first.evaluate(element => element.scrollIntoView({ block: 'start' }))
    await first.screenshot({ path: `${shots}/actions-${width}.png` })
    // Keyboard sorting must preserve the same text while changing its position.
    await page.getByRole('button', { name: '上移条目 2', exact: true }).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByLabel('条目 1', { exact: true })).toHaveValue(text)
    await page.getByRole('button', { name: '关联卡片', exact: true }).first().click()
    await expect(page.getByLabel('搜索要关联的卡片')).toBeVisible()
    await page.getByRole('button', { name: '关联卡片', exact: true }).first().click()
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    const save = page.getByRole('button', { name: '保存备忘', exact: true })
    await expect(save).toBeInViewport()
    if (width < 600) {
      const saveBox = await save.boundingBox(), navBox = await page.getByRole('navigation', { name: '移动端导航' }).boundingBox()
      expect(saveBox!.y + saveBox!.height).toBeLessThanOrEqual(navBox!.y)
    }
    await page.screenshot({ path: `${shots}/editor-bottom-${width}.png` })
  })
}
