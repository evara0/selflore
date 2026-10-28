import { expect, test, type Page } from '@playwright/test'
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { demoId, readDemo } from '../src/lib/demo'
import type { Card } from '../src/lib/workspace'

let server: ChildProcessWithoutNullStreams,
  previewUrl = ''
const samplePath = path.resolve('public/examples/paper-reading-checklist.json')
const sample = JSON.parse(readFileSync(samplePath, 'utf8'))
const user = {
  id: demoId(900),
  username: 'fixture_user',
  role: 'member',
  is_active: true,
  csrf_token: 'synthetic',
}

test.beforeAll(async () => {
  const python =
    process.env.SELFLORE_API_PYTHON ||
    path.resolve('../api/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  server = spawn(python, [path.resolve('../api/tests/import_preview_server.py')], {
    cwd: path.resolve('../api'),
    env: { ...process.env, SELFLORE_DATABASE_URL: '' },
    windowsHide: true,
  })
  let output = '',
    errors = ''
  server.stderr.on('data', (chunk) => {
    errors += chunk.toString()
  })
  const port = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('Import preview fixture startup timed out: ' + errors)),
      15000,
    )
    server.on('error', (error) => {
      clearTimeout(timer)
      reject(error)
    })
    server.on('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`Import preview fixture exited ${code}: ${errors}`))
    })
    server.stdout.on('data', (chunk) => {
      output += chunk.toString()
      const match = output.match(/IMPORT_PREVIEW_PORT=(\d+)/)
      if (match) {
        clearTimeout(timer)
        resolve(match[1])
      }
    })
  })
  previewUrl = `http://127.0.0.1:${port}/api/cards/import-preview`
  await expect
    .poll(async () => {
      try {
        return (await fetch(`http://127.0.0.1:${port}/api/health`)).status
      } catch {
        return 0
      }
    })
    .toBe(200)
})
test.afterAll(async () => {
  if (!server || server.exitCode !== null) return
  await new Promise<void>((resolve) => {
    server.once('exit', () => resolve())
    server.kill()
  })
})

async function fixture(page: Page, options: { guest?: boolean; failOnce?: boolean } = {}) {
  const writes: Record<string, unknown>[] = []
  let saved: Card | undefined,
    failed = false,
    previews = 0
  await page.route('**/api/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      endpoint = url.pathname.slice(4)
    if (endpoint === '/auth/me')
      return route.fulfill(options.guest ? { status: 401, json: {} } : { json: user })
    if (endpoint === '/auth/config') return route.fulfill({ json: { registration_enabled: true } })
    if (endpoint === '/cards/import-preview') {
      previews++
      const response = await route.fetch({
        url: previewUrl,
        headers: {
          ...request.headers(),
          Origin: 'http://import.test',
          'X-CSRF-Token': 'synthetic',
        },
      })
      return route.fulfill({ response })
    }
    if (endpoint === '/cards' && request.method() === 'POST') {
      const body = request.postDataJSON()
      writes.push(body)
      if (options.failOnce && !failed) {
        failed = true
        return route.fulfill({ status: 503, json: { detail: { message: '合成保存失败，请重试' } } })
      }
      saved = {
        ...body,
        id: demoId(910),
        code: '导入-910',
        revision: 1,
        lifecycle: 'active',
        tags: [],
        topics: [],
      } as Card
      return route.fulfill({ status: 201, json: saved })
    }
    if (saved && endpoint === '/cards/' + saved.id) return route.fulfill({ json: saved })
    if (endpoint.endsWith('/links')) return route.fulfill({ json: { incoming: [], outgoing: [] } })
    if (request.method() !== 'GET') throw new Error('Unexpected write: ' + endpoint)
    return route.fulfill({ json: readDemo(endpoint + url.search) })
  })
  return {
    writes,
    get previews() {
      return previews
    },
  }
}

for (const width of [320, 390, 1280]) {
  test(`global file import previews complete checklist and retries at ${width}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 844 })
    const state = await fixture(page, { failOnce: true })
    const folder = process.env.SELFLORE_CAPTURE_DIR || testInfo.outputPath('visual')
    await mkdir(folder, { recursive: true })
    const capture = async (name: string) => {
      await page.evaluate(() => document.fonts.ready)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await page.screenshot({ path: path.join(folder, `import-${width}-${name}.png`) })
    }
    await page.goto('/new')
    await expect(page.getByRole('heading', { name: '新建卡片', exact: true })).toBeVisible()
    await capture('manual')
    await page.getByRole('link', { name: 'JSON 导入', exact: true }).click()
    await capture('empty')
    const input = page.getByRole('textbox', { name: 'JSON 内容', exact: true })
    await input.fill('{"title":"缺少类别"}')
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('kind')
    await expect(input).toHaveValue('{"title":"缺少类别"}')
    await input.evaluate((element) =>
      element.scrollIntoView({ block: 'start', behavior: 'instant' }),
    )
    await capture('invalid')
    await page.getByLabel('选择 JSON 文件', { exact: true }).setInputFiles(samplePath)
    await expect(input).toHaveValue(readFileSync(samplePath, 'utf8').replace(/\r\n?/g, '\n'))
    await page.getByRole('button', { name: '校验并预览', exact: true }).click()
    const preview = page.getByRole('region', { name: '导入预览', exact: true })
    await expect(preview.getByRole('heading', { name: sample.title, exact: true })).toBeVisible()
    await expect(preview.getByRole('listitem')).toHaveCount(14) // three Markdown bullets plus eleven checklist rows
    await expect(preview.getByText('开放性', { exact: true })).toBeVisible()
    await expect(preview.getByText('未完成', { exact: true })).toHaveCount(11)
    expect(state.writes).toHaveLength(0)
    await preview
      .getByRole('heading', { name: sample.title, exact: true })
      .evaluate((element) => element.scrollIntoView({ block: 'start', behavior: 'instant' }))
    await capture('preview')
    await preview
      .getByText('安卓端', { exact: true })
      .evaluate((element) => element.scrollIntoView({ block: 'center', behavior: 'instant' }))
    await capture('columns')
    const save = page.getByRole('button', { name: '确认导入', exact: true })
    await save.evaluate((element) =>
      element.scrollIntoView({ block: 'center', behavior: 'instant' }),
    )
    await save.click()
    await expect(page.getByRole('alert')).toContainText('合成保存失败')
    await save.evaluate((element) =>
      element.scrollIntoView({ block: 'center', behavior: 'instant' }),
    )
    await capture('retry')
    await save.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/memos\/de000000-0000-4000-8000-000000000910$/)
    await expect(page.getByRole('heading', { name: sample.title, exact: true })).toBeVisible()
    expect(state.writes).toHaveLength(2)
    expect(state.writes[0]).toEqual(state.writes[1])
    const rows = state.writes[0].memo_items as {
      id: string
      is_completed: boolean
      extra_values: string[]
    }[]
    expect(rows).toHaveLength(11)
    expect(new Set(rows.map((row) => row.id)).size).toBe(11)
    expect(rows.every((row) => !row.is_completed)).toBe(true)
    expect(rows[0].extra_values).toEqual(sample.memo_items[0].extra_values)
  })
}

for (const content of [
  { kind: 'knowledge', form: 'qa', title: '导入问答', question_md: '问题', answer_md: '答案' },
  { kind: 'knowledge', form: 'cloze', title: '导入填空', body_md: '阅读 {{c1::论文}}' },
  { kind: 'opinion', title: '导入观点', body_md: '自己的观点' },
  { kind: 'reference', title: '导入资料', body_md: '原始摘录', note_md: '收录说明' },
  { kind: 'memo', memo_format: 'note', title: '导入普通备忘', body_md: '随手记录' },
]) {
  test(`pasted JSON routes ${content.title} by its own kind`, async ({ page }) => {
    const state = await fixture(page)
    await page.goto('/import')
    await page.getByRole('textbox', { name: 'JSON 内容' }).fill(JSON.stringify(content))
    await page.getByRole('button', { name: '校验并预览' }).click()
    await expect(
      page.getByRole('region', { name: '导入预览' }).getByRole('heading', { name: content.title }),
    ).toBeVisible()
    await page.getByRole('button', { name: '确认导入' }).click()
    await expect(page).toHaveURL(
      new RegExp(`/${content.kind === 'memo' ? 'memos' : 'cards'}/${demoId(910)}$`),
    )
    expect(state.writes).toHaveLength(1)
    expect(state.writes[0].kind).toBe(content.kind)
  })
}

test('editing invalidates preview, malformed imports keep content and drafts protect navigation', async ({
  page,
}) => {
  const state = await fixture(page)
  await page.goto('/import')
  const input = page.getByRole('textbox', { name: 'JSON 内容' })
  await input.fill(JSON.stringify(sample))
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('button', { name: '确认导入' })).toBeVisible()
  await input.fill('[]')
  await expect(page.getByRole('button', { name: '确认导入' })).not.toBeVisible()
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('alert')).toContainText('对象')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByRole('link', { name: '手动新建' }).click()
  await expect(page).toHaveURL(/\/import$/)
  await expect(input).toHaveValue('[]')
  await input.fill('')
  await page.getByRole('link', { name: '手动新建' }).click()
  await expect(page).toHaveURL(/\/new$/)
  expect(state.writes).toHaveLength(0)
})

test('guest import requires login and oversized file never reaches preview', async ({ page }) => {
  const guest = await fixture(page, { guest: true })
  await page.goto('/import')
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'JSON 内容' })).not.toBeVisible()
  expect(guest.previews).toBe(0)
  await page.unroute('**/api/**')
  const state = await fixture(page)
  await page.goto('/import')
  await page.getByLabel('选择 JSON 文件', { exact: true }).setInputFiles({
    name: 'large.json',
    mimeType: 'application/json',
    buffer: Buffer.alloc(1024 * 1024 + 1, 'a'),
  })
  await expect(page.getByRole('alert')).toContainText('1 MiB')
  expect(state.previews).toBe(0)
  expect(state.writes).toHaveLength(0)
  await page.getByLabel('选择 JSON 文件', { exact: true }).setInputFiles({
    name: 'invalid-utf8.json',
    mimeType: 'application/json',
    buffer: Buffer.from([0xff, 0xfe, 0x00]),
  })
  await expect(page.getByRole('alert')).toContainText('UTF-8')
  expect(state.previews).toBe(0)
  await page.getByLabel('选择 JSON 文件', { exact: true }).setInputFiles({
    name: 'valid-bom.json',
    mimeType: 'application/json',
    buffer: Buffer.from(
      '\ufeff' +
        JSON.stringify({
          kind: 'memo',
          memo_format: 'note',
          title: '有效编码',
          body_md: '保留替换符号：\ufffd',
        }),
    ),
  })
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(
    page.getByRole('region', { name: '导入预览' }).getByRole('heading', { name: '有效编码' }),
  ).toBeVisible()
})
