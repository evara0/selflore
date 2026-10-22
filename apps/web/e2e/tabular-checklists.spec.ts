import { test, expect, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import type { Card } from '../src/lib/workspace'

const base = 'http://127.0.0.1:24568'
const shots = path.resolve('../../.cache/frontend-visual-review/tabular-checklists')
async function api(page: Page, endpoint: string, body?: object, method = 'POST') {
  const token = (await (await page.request.get(base + '/api/auth/me')).json()).csrf_token
  const response = await page.request.fetch(base + '/api' + endpoint, { method, data: body, headers: { Origin: base, 'X-CSRF-Token': token } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
async function capture(page: Page, name: string) {
  await expect(page.getByText('正在加载页面…', { exact:true })).toHaveCount(0)
  await expect(page.getByText('正在加载…', { exact:true })).toHaveCount(0)
  await page.evaluate(() => document.fonts.ready)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: path.join(shots, name + '.png'), fullPage: true })
}
test('tabular checklist roundtrip, inline knowledge retry, drafts and responsive reading', async ({ page }) => {
  test.setTimeout(150000)
  if (process.env.SELFLORE_TEST_ISOLATED !== '1') throw new Error('Disposable service required')
  await mkdir(shots, { recursive: true })
  const username = 'table_' + randomUUID().slice(0,8), password = 'table-browser-pass-123'
  for (const action of ['register','login']) {
    const r = await page.request.post(base + '/api/auth/' + action, { data: { username, password }, headers: { Origin: base } })
    expect(r.ok(), await r.text()).toBeTruthy()
  }
  const tag = await api(page, '/tags', { name: '系统命令' })
  const existing = await api(page, '/cards', { kind: 'knowledge', form: 'qa', title: 'systemd 定时器解释', question_md: '如何列出定时器？', answer_md: 'systemctl list-timers', client_request_id: randomUUID() })
  await api(page, '/cards', { kind: 'opinion', title: '不应进入知识选择器', body_md: '合成观点', client_request_id: randomUUID() })
  const initialKnowledge = (await (await page.request.get(base + '/api/cards?kind=knowledge')).json()).total
  await page.goto('/new?kind=memo&memo_format=checklist')
  await page.getByLabel('标题', { exact: true }).fill('认识不同系统的定时任务')
  await page.getByLabel('清单说明（可选）').fill('合成验收样例；勾选仅表示学习安排完成。')
  await page.getByLabel('显示字段数').selectOption('3')
  for (const [i,name] of ['命令','适用系统','简要说明'].entries()) await page.getByLabel(`字段 ${i+1} 名称`).fill(name)
  for (let i=0;i<2;i++) await page.getByRole('button', { name: '＋ 添加条目' }).click()
  for (const [i,values] of [ ['crontab -l','Linux / macOS','查看当前用户的定时任务列表。'], ['systemctl list-timers','Linux','列出 systemd 的定时器与下次触发时间。'], ['schtasks','Windows','查询 Windows 任务计划，进一步解释见关联知识。'] ].entries()) {
    await page.getByLabel(`条目 ${i+1}`, { exact: true }).fill(values[0])
    await page.getByLabel(`条目 ${i+1} 适用系统`, { exact: true }).fill(values[1])
    await page.getByLabel(`条目 ${i+1} 简要说明`, { exact: true }).fill(values[2])
  }
  await page.getByRole('button', { name: /系统命令/ }).click()
  await page.getByRole('button', { name: '关联知识', exact: true }).nth(1).click()
  await expect(page.getByRole('button', { name: /不应进入知识选择器/ })).toHaveCount(0)
  await page.getByRole('button', { name: /systemd 定时器解释/ }).click()
  await page.getByLabel('显示字段数').selectOption('1')
  await page.getByLabel('显示字段数').selectOption('3')
  await expect(page.getByLabel('条目 3 简要说明')).toHaveValue('查询 Windows 任务计划，进一步解释见关联知识。')
  // A cancelled knowledge form keeps the entire parent mounted and returns focus to its row.
  await page.getByRole('button', { name: '新建知识并关联' }).nth(2).click()
  await page.getByRole('button', { name: '取消新建知识' }).click()
  await expect(page.getByLabel('条目 3', { exact: true })).toBeFocused()
  await expect(page.getByLabel('条目 1', { exact: true })).toHaveValue('crontab -l')
  await page.getByRole('button', { name: '新建知识并关联' }).first().click()
  const inline = page.getByRole('region', { name: '当前行新建知识' })
  await inline.getByLabel('标题', { exact: true }).fill('crontab 命令解释')
  await inline.getByLabel('问题', { exact: true }).fill('crontab -l 显示什么？')
  await inline.getByLabel('答案', { exact: true }).fill('显示当前用户的定时任务，不会修改任务。')
  let lost = false
  const requests: string[] = []
  await page.route('**/api/cards', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = route.request().postDataJSON()
    if (body.kind !== 'knowledge') return route.continue()
    requests.push(body.client_request_id)
    if (!lost) { lost=true; await route.fetch(); return route.fulfill({ status:503, json:{ detail:{ message:'合成：知识已写入但响应丢失，请重试' } } }) }
    return route.continue()
  })
  await inline.getByRole('button', { name: '保存卡片' }).click()
  await expect(inline.getByRole('status')).toContainText('响应丢失')
  await page.setViewportSize({ width:390, height:844 })
  await capture(page,'knowledge-retry-390')
  await inline.getByRole('status').scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(shots,'knowledge-retry-viewport-390.png')})
  await inline.getByRole('button', { name: '保存卡片' }).click()
  await expect(page.getByText(/已新建 1 张知识并独立保存/)).toBeVisible()
  expect(requests).toHaveLength(2); expect(requests[0]).toBe(requests[1])
  expect((await (await page.request.get(base + '/api/cards?kind=knowledge')).json()).total).toBe(initialKnowledge + 1)
  await page.unroute('**/api/cards')
  // Exercise cloze rules in the same reusable editor, including server validation.
  await page.getByRole('button', { name: '新建知识并关联' }).nth(2).click()
  await inline.getByLabel('标题', { exact: true }).fill('Windows 计划任务解释')
  await inline.getByLabel('卡片形式').selectOption('cloze')
  await inline.getByLabel('填空正文').fill('schtasks 用于查询任务计划。')
  await inline.getByRole('button', { name: '保存卡片' }).click()
  await expect(inline.getByRole('status')).not.toBeEmpty()
  await inline.getByLabel('填空正文').fill('Windows 可用 {{c1::schtasks}} 查询任务计划。')
  await inline.getByRole('button', { name: '保存卡片' }).click()
  await expect(page.getByText(/已新建 2 张知识并独立保存/)).toBeVisible()
  for (const width of [320,390,1280]) {
    await page.setViewportSize({ width,height:width===1280?900:844 })
    await capture(page,`checklist-editor-${width}`)
    if (width === 320 || width === 1280) {
      await (width === 320 ? page.locator('.checklist-row-fields').first().locator('label').nth(1) : page.locator('.tabular-edit > li').first()).screenshot({ path:path.join(shots,`editor-row-${width}.png`) })
    }
    if (width === 390) {
      await page.evaluate(() => window.scrollTo(0,document.documentElement.scrollHeight))
      await page.getByRole('button',{name:'保存备忘'}).scrollIntoViewIfNeeded()
      const save=await page.getByRole('button',{name:'保存备忘'}).boundingBox()
      const nav=await page.getByRole('navigation',{name:'移动端导航'}).boundingBox()
      expect(save!.y+save!.height).toBeLessThan(nav!.y)
      await page.screenshot({path:path.join(shots,'editor-save-viewport-390.png')})
    }
  }
  // Sort with keyboard; completion state travels with the same row.
  await page.getByRole('checkbox', { name:'已完成' }).nth(2).check()
  await page.getByRole('button', { name:'上移条目 3', exact:true }).focus(); await page.keyboard.press('Enter')
  await expect(page.getByLabel('条目 2', { exact:true })).toHaveValue('schtasks')
  let failedMemo = false
  await page.route('**/api/cards', async route => {
    if (route.request().method()==='POST' && route.request().postDataJSON().kind==='memo' && !failedMemo) {
      failedMemo=true; return route.fulfill({status:503,json:{detail:{message:'合成：清单保存失败，请重试'}}})
    }
    return route.continue()
  })
  await page.getByRole('button', { name:'保存备忘' }).click()
  await expect(page.getByText('合成：清单保存失败，请重试')).toBeVisible()
  await page.setViewportSize({width:390,height:844}); await capture(page,'checklist-save-error-390')
  await expect(page.getByText(/知识不会被删除/)).toBeVisible()
  await page.getByRole('button', { name:'保存备忘' }).click()
  await expect(page).toHaveURL(/\/memos\/[a-f0-9-]+$/)
  const memoUrl=page.url(), memoId=memoUrl.split('/').pop()!
  await page.unroute('**/api/cards')
  await page.reload()
  await expect(page.getByRole('heading', {name:'认识不同系统的定时任务'})).toBeVisible()
  const card: Card=await (await page.request.get(base+'/api/cards/'+memoId)).json()
  expect(card.memo_items?.map(i=>i.text)).toEqual(['crontab -l','schtasks','systemctl list-timers'])
  expect(card.tag_ids).toEqual([tag.id]); expect(card.memo_items?.[1].is_completed).toBe(true)
  expect(card.memo_items?.[2].target_ids).toContain(existing.id)
  for (const width of [320,390,1280]) {
    await page.setViewportSize({width,height:width===1280?900:844}); await capture(page,`checklist-detail-${width}`)
  }
  await page.getByRole('link', {name:'crontab 命令解释 ↗'}).click()
  await expect(page.getByRole('heading', {name:'crontab 命令解释'})).toBeVisible()
  await page.goto(memoUrl)
  await page.getByRole('link', {name:'编辑卡片 ↗'}).click()
  await page.getByLabel('显示字段数').selectOption('1'); await page.getByRole('button', {name:'保存备忘'}).click()
  await expect(page).toHaveURL(memoUrl)
  await page.getByRole('link', {name:'编辑卡片 ↗'}).click()
  await page.getByLabel('显示字段数').selectOption('3')
  await expect(page.getByLabel('条目 2 适用系统')).toHaveValue('Windows')
  await page.getByRole('button', {name:'保存备忘'}).click(); await expect(page).toHaveURL(memoUrl)
  await page.setViewportSize({width:390,height:844})
  await page.goto('/memos?view=open&q=systemd')
  await expect(page.getByText('1 项未完成事项')).toBeVisible()
  await capture(page,'open-items-390')
  const group=await api(page,'/collections',{title:'系统命令学习',client_request_id:randomUUID()})
  await api(page,'/collections/'+group.id+'/items',{expected_revision:1,card_ids:[memoId]})
  await page.setViewportSize({width:1280,height:900}); await page.goto('/collections/'+group.id+'?view=read')
  await expect(page.getByText('crontab -l',{exact:true})).toBeVisible(); await capture(page,'collection-reader-1280')
  // Representative uses of shared frame; no extra writes.
  for (const [kind,width] of [['memo',390],['knowledge',320],['opinion',1280],['reference',390]] as const) {
    await page.setViewportSize({width,height:width===1280?900:844}); await page.goto('/new?kind='+kind)
    await expect(page.getByLabel('标题',{exact:true})).toBeVisible(); await capture(page,`${kind}-shared-editor-${width}`)
  }
})
