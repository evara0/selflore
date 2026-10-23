import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { readDemo } from '../src/lib/demo'

test('独立API替身下检查导入导出全部反馈状态', async ({ page }) => {
  const output = path.resolve(
    process.env.SELFLORE_CAPTURE_DIR ||
      '../../.cache/frontend-visual-review/card-json-transfer-layout',
  )
  await mkdir(output, { recursive: true })
  let valid = false
  let importing = false
  let release: (() => void) | undefined
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url()),
      endpoint = url.pathname.slice(4)
    if (endpoint === '/auth/me')
      return route.fulfill({
        json: {
          id: 'synthetic',
          username: 'fixture_user',
          role: 'member',
          is_active: true,
          csrf_token: 'synthetic',
        },
      })
    if (endpoint === '/auth/config') return route.fulfill({ json: { allow_registration: true } })
    if (endpoint === '/card-transfer/validate')
      return valid
        ? route.fulfill({ json: { digest: 'a'.repeat(64), card_count: 6, asset_count: 1 } })
        : route.fulfill({
            status: 422,
            json: {
              detail: {
                message: '交换格式校验失败',
                errors: [
                  {
                    card_key: 'AI生成的待核查资料卡片_长名称',
                    path: 'cards.AI生成的待核查资料卡片_长名称.memo_items.199.extra_values.1',
                    message: '附加文字超过2000字符，请修正文件后重新预检',
                  },
                ],
              },
            },
          })
    if (endpoint === '/card-transfer/import') {
      importing = true
      await new Promise<void>((resolve) => {
        release = resolve
      })
      return route.fulfill({ json: { card_count: 6, asset_count: 1, mapping: {} } })
    }
    if (endpoint === '/card-transfer/export')
      return route.fulfill({
        status: 503,
        json: { detail: { message: '原图缺失或存储不可用，无法完整导出' } },
      })
    return route.fulfill({ json: readDemo(endpoint + url.search) })
  })
  await page.goto('/me')
  const panel = page.getByRole('region', { name: '卡片导入导出' })
  await expect(panel).toBeVisible()
  async function tail(width: number, state: string) {
    const feedback = panel.getByRole('status')
    await feedback.scrollIntoViewIfNeeded()
    await page.evaluate(() => window.scrollBy(0, 130))
    await page.screenshot({ path: path.join(output, `${width}-${state}-viewport.png`) })
  }
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: width < 600 ? 844 : 900 })
    await page.evaluate(() => document.fonts.ready)
    const help = panel.locator('details')
    await expect(help).not.toHaveAttribute('open', '')
    await panel.screenshot({ path: path.join(output, `${width}-compact.png`) })
    await panel.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await page.screenshot({ path: path.join(output, `${width}-compact-viewport.png`) })
    await panel.getByText('格式与说明', { exact: true }).focus()
    await page.keyboard.press('Enter')
    await expect(help).toHaveAttribute('open', '')
    await panel.screenshot({ path: path.join(output, `${width}-help.png`) })
    await help.locator('p').last().scrollIntoViewIfNeeded()
    await page.evaluate(() => window.scrollBy(0, 130))
    await page.screenshot({ path: path.join(output, `${width}-help-viewport.png`) })
    await panel.getByText('格式与说明', { exact: true }).click()
    const file = page.getByLabel('JSON或ZIP文件')
    await file.focus()
    await page.screenshot({ path: path.join(output, `${width}-file-focus.png`) })
    const choosing = page.waitForEvent('filechooser')
    await page.keyboard.press('Space')
    await (await choosing).setFiles([])
    await file.hover()
    await panel.screenshot({ path: path.join(output, `${width}-file-hover.png`) })
    await file.setInputFiles({
      name: 'AI生成内容_需要确认来源与引用关系_长文件名.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{}'),
    })
    valid = false
    await page.getByRole('button', { name: '预检文件', exact: true }).click()
    await expect(panel.getByRole('alert')).toBeVisible()
    await panel.screenshot({ path: path.join(output, `${width}-error.png`) })
    await tail(width, 'error')
    valid = true
    await file.setInputFiles({
      name: '已修正的AI生成内容.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{}'),
    })
    await page.getByRole('button', { name: '预检文件', exact: true }).click()
    await expect(panel.getByText(/预检内容：6 张卡片/)).toBeVisible()
    await panel.screenshot({ path: path.join(output, `${width}-preview.png`) })
    await tail(width, 'preview')
    const confirm = page.getByRole('button', { name: '确认导入新卡片' })
    await confirm.focus()
    await page.keyboard.press('Enter')
    await expect(panel.getByRole('status')).toHaveText('正在处理，请稍候…')
    await expect(confirm).toBeDisabled()
    await panel.screenshot({ path: path.join(output, `${width}-pending.png`) })
    await tail(width, 'pending')
    expect(importing).toBe(true)
    release?.()
    await expect(panel.getByRole('status')).toHaveText('导入成功：6 张卡片，1 张图片。')
    await panel.screenshot({ path: path.join(output, `${width}-success.png`) })
    await tail(width, 'success')
    await page.getByRole('button', { name: '导出全部卡片' }).click()
    await expect(panel.getByRole('status')).toContainText('原图缺失')
    await panel.screenshot({ path: path.join(output, `${width}-export-error.png`) })
    await tail(width, 'export-error')
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.screenshot({ path: path.join(output, `${width}-page-bottom.png`), fullPage: true })
    await page.getByRole('button', { name: '开始新批次' }).click()
  }
})
