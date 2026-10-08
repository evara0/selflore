// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'

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
  expect(screen.queryByRole('button', { name: '管理用户' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '退出登录' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '登录' })).toBeTruthy())
  expect(calls).toContain('POST /api/auth/logout')
})
