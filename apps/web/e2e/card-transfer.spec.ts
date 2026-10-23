import { test, expect } from '@playwright/test'
import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'

test('真实接口导入导出及三种宽度视觉证据', async ({ page, baseURL }) => {
  test.setTimeout(120000)
  if (process.env.SELFLORE_TEST_ISOLATED !== '1' || baseURL !== 'http://127.0.0.1:24568')
    throw new Error('仅允许显式隔离本机24568环境')
  const capture = path.resolve('../../.cache/frontend-visual-review/card-json-transfer')
  await mkdir(capture, { recursive: true })
  const username = `transfer_${Date.now()}`
  const password = 'long-transfer-browser-password-123'
  const headers = { Origin: baseURL }
  const registered = await page.request.post('/api/auth/register', {
    data: { username, password },
    headers,
  })
  expect(registered.status(), await registered.text()).toBe(201)
  expect(
    (
      await page.request.post('/api/auth/login', { data: { username, password }, headers })
    ).status(),
  ).toBe(200)
  const example = await readFile(path.resolve('../../docs/card-transfer/example.json'))
  await page.goto('/me')
  const panel = page.getByRole('region', { name: '卡片导入导出' })
  await expect(panel).toBeVisible()
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.evaluate(() => document.fonts.ready)
    await panel.screenshot({ path: path.join(capture, `${width}-initial.png`) })
    const invalid = JSON.parse(example.toString())
    invalid.cards[0].answer_md = ''
    await page
      .getByLabel('JSON或ZIP文件')
      .setInputFiles({
        name: '无效内容_需要检查字段路径_长文件名.json',
        mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(invalid)),
      })
    await page.getByRole('button', { name: '预检文件', exact: true }).click()
    await expect(panel.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('button', { name: '确认导入新卡片' })).toBeDisabled()
    await panel.screenshot({ path: path.join(capture, `${width}-error.png`) })
    await page
      .getByLabel('JSON或ZIP文件')
      .setInputFiles({
        name: 'AI生成内容_包含六种卡片形式_完整示例.json',
        mimeType: 'application/json',
        buffer: example,
      })
    await page.getByRole('button', { name: '预检文件', exact: true }).click()
    await expect(panel.getByText(/预检内容：6 张卡片/)).toBeVisible()
    await panel.screenshot({ path: path.join(capture, `${width}-preview.png`) })
    const confirm = page.getByRole('button', { name: '确认导入新卡片' })
    await confirm.focus()
    await page.keyboard.press('Enter')
    await expect(panel.getByRole('status')).toContainText('导入成功：6 张卡片')
    await panel.screenshot({ path: path.join(capture, `${width}-imported.png`) })
    await page.getByLabel('导出格式').selectOption('json')
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出全部卡片' }).click()
    const jsonFile = await download
    await jsonFile.saveAs(path.join(capture, `${width}-export.json`))
    const exported = JSON.parse(await readFile(path.join(capture, `${width}-export.json`), 'utf8'))
    expect(exported.cards).toHaveLength((width === 320 ? 1 : width === 390 ? 2 : 3) * 6)
    await expect(panel.getByRole('status')).toContainText('完整导出已下载')
    await panel.screenshot({ path: path.join(capture, `${width}-exported.png`) })
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await expect(page.getByRole('button', { name: '开始新批次' })).toBeEnabled()
    await page.getByRole('button', { name: '开始新批次' }).click()
  }
  await page.getByLabel('导出格式').selectOption('zip')
  const zipDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出全部卡片' }).click()
  await (await zipDownload).saveAs(path.join(capture, 'browser-roundtrip.zip'))
  await page.getByLabel('JSON或ZIP文件').setInputFiles(path.join(capture, 'browser-roundtrip.zip'))
  await page.getByRole('button', { name: '预检文件', exact: true }).click()
  await expect(panel.getByText(/预检内容：18 张卡片/)).toBeVisible()
  await page.getByRole('button', { name: '确认导入新卡片' }).click()
  await expect(panel.getByRole('status')).toContainText('导入成功：18 张卡片')
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.screenshot({ path: path.join(capture, '1280-page-bottom.png'), fullPage: true })
})
