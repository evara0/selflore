// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { registrationRules } from './lib/registration'

const admin = { id: '00000000-0000-0000-0000-000000000001', username: 'keeper', role: 'admin', is_active: true, csrf_token: 'csrf-test' }
const member = { id: '00000000-0000-0000-0000-000000000002', username: 'alice', role: 'member', is_active: true }
const json = (data: object, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

beforeEach(() => {
  history.replaceState(null, '', '/knowledge')
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('closed registration is hidden and login errors are shown', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/auth/config') return json({ registration_enabled: false })
    if (path === '/api/auth/me') return json({ detail: '请先登录' }, 401)
    if (path === '/api/auth/login') return json({ detail: '用户名或密码错误' }, 401)
    throw new Error(path)
  }))
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: /登录/ }))
  await waitFor(() => expect(screen.queryByRole('tab', { name: '注册' })).toBeNull())
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'alice' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrong-password' } })
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登录' }))
  await waitFor(() => expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toContain('用户名或密码错误'))
})

test('register then login updates the account entry', async () => {
  let loggedIn = false
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/auth/config') return json({ registration_enabled: true })
    if (path === '/api/auth/me') return loggedIn ? json({ ...member, csrf_token: 'csrf-member' }) : json({ detail: '请先登录' }, 401)
    if (path === '/api/auth/register') return json(member, 201)
    if (path === '/api/auth/login') { loggedIn = true; return json(member) }
    throw new Error(path)
  }))
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: /登录/ }))
  fireEvent.click(await screen.findByRole('tab', { name: '注册' }))
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'alice' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'a-long-test-password-123' } })
  fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'a-long-test-password-123' } })
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '注册' }))
  await waitFor(() => expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toContain('注册成功'))
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'a-long-test-password-123' } })
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登录' }))
  await waitFor(() => expect(screen.getByRole('button', { name: /alice/ })).toBeTruthy())
})

test('existing session restores account and admin mutation sends CSRF token', async () => {
  const calls: { path: string; method: string; token?: string }[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    const headers = init?.headers as Record<string, string> | undefined
    calls.push({ path, method: init?.method || 'GET', token: headers?.['X-CSRF-Token'] })
    if (path === '/api/auth/config') return json({ registration_enabled: false })
    if (path === '/api/auth/me') return json(admin)
    if (path === '/api/admin/users?limit=20&offset=0') return json({ items: [admin, member], total: 2, limit: 20, offset: 0 })
    if (path === `/api/admin/users/${member.id}`) return json({ ...member, is_active: false })
    throw new Error(path)
  }))
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: /keeper/ })).toBeTruthy())
  fireEvent.click(screen.getByRole('button', { name: /keeper/ }))
  fireEvent.click(await screen.findByRole('button', { name: '管理用户' }))
  await waitFor(() => expect(screen.getByText('alice')).toBeTruthy())
  expect(screen.getByLabelText('初始密码（至少 8 个字符）').getAttribute('minlength')).toBe('8')
  const createForm = screen.getByLabelText('初始密码（至少 8 个字符）').closest('form')!
  const newUsername = within(createForm).getByLabelText('用户名') as HTMLInputElement
  newUsername.value = '123中文'
  expect(newUsername.checkValidity()).toBe(true)
  fireEvent.click(within(screen.getByText('alice').closest('.user-row') as HTMLElement).getByRole('button', { name: '停用' }))
  await waitFor(() => expect(calls.some((call) => call.path === `/api/admin/users/${member.id}` && call.method === 'PATCH' && call.token === 'csrf-test')).toBe(true))
})

test('member can open account and logout resets the interface', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    calls.push(`${init?.method || 'GET'} ${path}`)
    if (path === '/api/auth/config') return json({ registration_enabled: false })
    if (path === '/api/auth/me') return json({ ...member, csrf_token: 'csrf-member' })
    if (path === '/api/auth/logout') return new Response(null, { status: 204 })
    throw new Error(path)
  }))
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: /alice/ })).toBeTruthy())
  fireEvent.click(screen.getByRole('button', { name: /alice/ }))
  expect(screen.getByLabelText('新密码（至少 8 个字符）').getAttribute('minlength')).toBe('8')
  expect(screen.queryByRole('button', { name: '管理用户' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '退出登录' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '登录' })).toBeTruthy())
  expect(calls).toContain('POST /api/auth/logout')
})

async function openRegistration(registerResponse: () => Promise<Response> = async () => json(member, 201)) {
  const fetchMock = vi.fn(async (path: string) => {
    if (path === '/api/auth/config') return json({ registration_enabled: true })
    if (path === '/api/auth/me') return json({ detail: '请先登录' }, 401)
    if (path === '/api/auth/register') return registerResponse()
    throw new Error(path)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  fireEvent.click(await screen.findByRole('tab', { name: '注册' }))
  return { fetchMock, dialog: screen.getByRole('dialog'), username: screen.getByLabelText('用户名'), password: screen.getByLabelText('密码'), confirmation: screen.getByLabelText('确认密码') }
}

function fillRegistration(username = 'alice', password = 'a'.repeat(8), confirmation = password) {
  for (const [label, value] of [['用户名', username], ['密码', password], ['确认密码', confirmation]]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }
}

test('registration shows two short hints without a repeated summary', async () => {
  const { dialog, username, password, confirmation } = await openRegistration()
  for (const rule of Object.values(registrationRules).filter(Boolean)) expect(within(dialog).getByText(rule)).toBeTruthy()
  for (const field of [username, password, confirmation]) expect(field.getAttribute('aria-invalid')).toBe('false')
  expect(dialog.querySelectorAll('.auth-error')).toHaveLength(0)
  const submit = within(dialog).getByRole('button', { name: '注册' })
  expect(submit).toHaveProperty('disabled', true)
  expect(dialog.querySelector('.auth-summary')).toBeNull()
  expect(dialog.querySelectorAll('.auth-rule')).toHaveLength(2)
  fillRegistration('alice', 'short', 'different')
  expect(submit).toHaveProperty('disabled', true)
  expect(dialog.querySelectorAll('.auth-error')).toHaveLength(0)
  fillRegistration()
  expect(submit).toHaveProperty('disabled', false)
  expect(dialog.querySelector('.auth-summary')).toBeNull()
  for (const rule of Object.values(registrationRules).filter(Boolean)) expect(within(dialog).getByText(rule)).toBeTruthy()
})

test('blur errors are linked to fields and corrections including changed passwords update immediately', async () => {
  const { dialog, username, password, confirmation } = await openRegistration()
  fireEvent.blur(username)
  expect(document.getElementById('register-username-feedback')?.textContent).toBe('请填写用户名')
  fireEvent.change(username, { target: { value: 'a@b' } })
  expect(document.getElementById('register-username-feedback')?.textContent).toContain('请用中文')
  expect(username.getAttribute('aria-invalid')).toBe('true')
  expect(within(dialog).queryByText(registrationRules.username)).toBeNull()
  expect(username.getAttribute('aria-describedby')).toBe('register-username-feedback')
  fireEvent.change(username, { target: { value: 'alice' } })
  expect(username.getAttribute('aria-invalid')).toBe('false')
  expect(within(dialog).getByText(registrationRules.username)).toBeTruthy()
  expect(username.getAttribute('aria-describedby')).toBe('register-username-feedback')
  fireEvent.blur(password)
  expect(document.getElementById('register-password-feedback')?.textContent).toBe('请填写密码')
  fireEvent.change(password, { target: { value: 'short' } })
  expect(document.getElementById('register-password-feedback')?.textContent).toContain('至少 8 位')
  fireEvent.blur(confirmation)
  expect(document.getElementById('register-confirmation-feedback')?.textContent).toBe('请再次输入密码')
  fillRegistration('alice', 'a'.repeat(8), 'different')
  expect(document.getElementById('register-confirmation-feedback')?.textContent).toContain('不一致')
  fillRegistration()
  expect(dialog.querySelectorAll('.auth-error')).toHaveLength(0)
  fireEvent.change(password, { target: { value: 'b'.repeat(8) } })
  expect(confirmation.getAttribute('aria-invalid')).toBe('true')
  fireEvent.change(confirmation, { target: { value: 'b'.repeat(8) } })
  expect(confirmation.getAttribute('aria-invalid')).toBe('false')
  for (const field of [username, password]) expect(document.getElementById(field.getAttribute('aria-describedby')!)).toBeTruthy()
  expect(confirmation.hasAttribute('aria-describedby')).toBe(false)
  expect(dialog.querySelector('.auth-summary')).toBeNull()
})

test('mode changes and closing clear registration errors without applying its limits to login', async () => {
  const { dialog, password } = await openRegistration()
  fillRegistration('alice', 'short', 'different')
  fireEvent.blur(password)
  expect(dialog.querySelector('.auth-error')).toBeTruthy()
  fireEvent.click(within(dialog).getByRole('tab', { name: '登录' }))
  expect(dialog.querySelector('.auth-error')).toBeNull()
  expect(screen.queryByLabelText('确认密码')).toBeNull()
  expect(password.hasAttribute('aria-invalid')).toBe(false)
  expect(within(dialog).getByRole('button', { name: '登录' })).toHaveProperty('disabled', false)
  fireEvent.click(within(dialog).getByRole('tab', { name: '注册' }))
  expect(dialog.querySelector('.auth-error')).toBeNull()
  fireEvent.blur(password)
  expect(dialog.querySelector('.auth-error')).toBeTruthy()
  fireEvent.click(within(dialog).getByRole('button', { name: '关闭登录窗口' }))
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  fireEvent.click(await screen.findByRole('tab', { name: '注册' }))
  expect(dialog.querySelectorAll('.auth-error')).toHaveLength(0)
  expect(password).toHaveProperty('value', '')
})

test('invalid direct submissions never reach the API and in-flight submissions cannot repeat', async () => {
  let finish!: (response: Response) => void
  const { fetchMock, dialog } = await openRegistration(() => new Promise(resolve => { finish = resolve }))
  const form = dialog.querySelector('form')!
  fireEvent.submit(form)
  fillRegistration('alice', 'short', 'short')
  fireEvent.submit(form)
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/auth/register')).toHaveLength(0)
  fillRegistration()
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/auth/register')).toHaveLength(1)
  expect(within(dialog).getByRole('button', { name: '请稍候…' })).toHaveProperty('disabled', true)
  expect(within(dialog).getByRole('status').textContent).toContain('正在提交')
  finish(json(member, 201))
  await waitFor(() => expect(within(dialog).getByRole('status').textContent).toContain('注册成功'))
  expect(dialog.querySelector('.auth-summary')).toBeNull()
  expect(dialog.querySelectorAll('.auth-error')).toHaveLength(0)
})

test.each([[409, '用户名已存在'], [429, '请求过于频繁']])('registration %i errors remain visible and allow retry', async (status, message) => {
  const { dialog } = await openRegistration(async () => json({ detail: message }, status))
  fillRegistration()
  fireEvent.click(within(dialog).getByRole('button', { name: '注册' }))
  await waitFor(() => expect(within(dialog).getByRole('status').textContent).toBe(message))
  expect(dialog.querySelector('.auth-summary')).toBeNull()
  expect(within(dialog).getByRole('button', { name: '注册' })).toHaveProperty('disabled', false)
})

test.each(['中文用户', '123用户'])('register and login enable the new username %s with eight characters', async username => {
  const { dialog } = await openRegistration()
  fillRegistration(username)
  expect(within(dialog).getByRole('button', { name: '注册' })).toHaveProperty('disabled', false)
  fireEvent.click(within(dialog).getByRole('tab', { name: '登录' }))
  expect(within(dialog).getByRole('button', { name: '登录' })).toHaveProperty('disabled', false)
})
