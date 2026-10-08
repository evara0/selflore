import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card } from '../src/lib/workspace'

const shots = '../../docs/design/card-navigation-v1/mobile-create'

for (const authenticated of [false, true]) {
  test(`mobile central create: ${authenticated ? 'authenticated editor and save' : 'guest login gate'}`, async ({ page }) => {
    const writes: string[] = []
    let saved: Card | undefined
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.slice(4)
      if (path === '/auth/me') {
        await route.fulfill(authenticated
          ? { json: { id: demoId(900), username: 'mobileuser', role: 'member', is_active: true, csrf_token: 'mobile-test-token' } }
          : { status: 401, json: { detail: '请先登录' } })
      } else if (path === '/auth/config') {
        await route.fulfill({ json: { registration_enabled: true } })
      } else if (authenticated && path === '/cards' && request.method() === 'POST') {
        writes.push(path)
        expect(request.headers()['x-csrf-token']).toBe('mobile-test-token')
        saved = { ...readDemo<Card>(`/cards/${demoId(1)}`), ...request.postDataJSON(), id: demoId(999), code: 'MOBILE-TEST', revision: 1 }
        await route.fulfill({ status: 201, json: saved })
      } else if (authenticated && request.method() === 'GET') {
        const json = saved && path === `/cards/${saved.id}` ? saved
          : saved && path === `/cards/${saved.id}/links` ? { incoming: [], outgoing: [] }
          : readDemo(path + url.search)
        await route.fulfill({ json })
      } else {
        writes.push(`${request.method()} ${path}`)
        await route.abort()
      }
    })
    await mkdir(shots, { recursive: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/knowledge')
    const navigation = page.getByRole('navigation', { name: '移动端导航' })
    const create = navigation.getByRole('link', { name: '新建', exact: true })
    await expect(create).toBeVisible()
    await expect(page.getByRole('link', { name: '主动回忆为什么有效？', exact: true })).toBeVisible()
    await expect(navigation.getByRole('link').locator('span:not([aria-hidden])')).toHaveText(['知识', '观点', '新建', '合集', '我的'])
    await expect(page.locator('.header-actions .create-action')).toBeHidden()

    for (const width of [320, 390, 600]) {
      await page.setViewportSize({ width, height: 844 })
      const bounds = await create.boundingBox()
      expect(bounds).not.toBeNull()
      expect(Math.abs(bounds!.x + bounds!.width / 2 - width / 2)).toBeLessThan(1)
      for (const link of await navigation.getByRole('link').all()) {
        const box = await link.boundingBox()
        expect(box!.width).toBeGreaterThanOrEqual(44)
        expect(box!.height).toBeGreaterThanOrEqual(44)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: `${shots}/${authenticated ? 'member' : 'guest'}-mobile.png` })
    const before = await create.boundingBox()
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
    await expect.poll(async () => (await create.boundingBox())!.y).toBeCloseTo(before!.y, 1)
    await page.screenshot({ path: `${shots}/${authenticated ? 'member' : 'guest'}-mobile-scrolled.png` })

    await create.tap()
    await expect(page).toHaveURL(/\/new$/)
    if (authenticated) {
      await expect(page.getByRole('heading', { name: '新建卡片' })).toBeVisible()
      await expect(page.getByRole('button', { name: '事实知识', exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: '原子观点', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: '新建合集 ↗', exact: true })).toBeVisible()
      await page.getByLabel('标题', { exact: true }).fill('移动底栏创建的知识')
      await page.getByLabel('问题', { exact: true }).fill('如何从移动端新建？')
      await page.getByLabel('答案', { exact: true }).fill('点击底栏中央的新建入口。')
      await page.getByRole('button', { name: '保存卡片', exact: true }).tap()
      await expect(page).toHaveURL(new RegExp(`/knowledge/cards/${demoId(999)}$`))
      await expect(page.getByRole('heading', { name: '移动底栏创建的知识' })).toBeVisible()
      expect(writes).toEqual(['/cards'])
    } else {
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByRole('tab', { name: '注册', exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: '保存卡片', exact: true })).toHaveCount(0)
      expect(writes).toEqual([])
      await page.getByRole('button', { name: '关闭登录窗口' }).tap()
    }

    for (const [label, path] of [['知识', '/knowledge'], ['观点', '/opinions'], ['合集', '/collections'], ['我的', '/me']]) {
      await navigation.getByRole('link', { name: label, exact: true }).tap()
      await expect(page).toHaveURL(new RegExp(`${path}$`))
      await expect(navigation.getByRole('link', { name: label, exact: true })).toHaveAttribute('aria-current', 'page')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    await expect(page.locator('.profile-panel')).toBeVisible()
    await page.setViewportSize({ width: 1586, height: 992 })
    await expect(navigation).toBeHidden()
    await expect(page.locator('.header-actions .create-action')).toBeVisible()
    await page.screenshot({ path: `${shots}/${authenticated ? 'member' : 'guest'}-desktop.png`, fullPage: true })
  })
}
