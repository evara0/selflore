// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import SourceCapture from './features/cards/SourceCapture'

const { api } = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('./lib/workspace', () => ({ useApi: () => api }))
const apply = vi.fn()
const result = {
  category: 'x',
  method: 'webpage',
  status: 'partial',
  fallback_reason: 'timeout',
  fields: { source_title: '来源建议' },
}
function Harness() {
  const [url, setUrl] = useState('')
  return <SourceCapture url={url} onUrlChange={setUrl} onApply={apply} />
}
function fill(value = 'https://x.com/author/status/123') {
  fireEvent.change(screen.getByLabelText('收录链接'), { target: { value } })
}
function click() {
  fireEvent.click(screen.getByRole('button', { name: '获取来源信息' }))
}
beforeEach(() => {
  api.mockReset()
  apply.mockClear()
})
afterEach(cleanup)

test('paste waits for explicit fetch and sends mode through the existing API client', async () => {
  api.mockResolvedValue(result)
  render(<Harness />)
  fill()
  expect(api).not.toHaveBeenCalled()
  click()
  await screen.findByText(/已回退普通网页/)
  expect(api).toHaveBeenCalledWith('/sources/resolve', 'POST', {
    url: 'https://x.com/author/status/123',
    mode: 'auto',
  })
  expect(apply).toHaveBeenCalledWith(result.fields)
})

test('invalid URL does not invoke the endpoint', () => {
  render(<Harness />)
  fill('not a URL')
  click()
  expect(screen.getByRole('status').textContent).toContain('完整的')
  expect(api).not.toHaveBeenCalled()
})

test('A to B to A invalidates an old response, and permits a new request', async () => {
  let complete!: (value: unknown) => void
  api.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
  )
  api.mockResolvedValue(result)
  render(<Harness />)
  fill()
  click()
  expect((screen.getByRole('button', { name: '获取中…' }) as HTMLButtonElement).disabled).toBe(true)
  fill('https://example.com/b')
  fill()
  await act(async () => complete(result))
  expect(apply).not.toHaveBeenCalled()
  click()
  await screen.findByText(/已回退普通网页/)
  expect(apply).toHaveBeenCalledTimes(1)
})

test('changing method and unmounting both invalidate in-flight results', async () => {
  let complete!: (value: unknown) => void
  api.mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
  )
  const view = render(<Harness />)
  fill()
  click()
  fireEvent.change(screen.getByLabelText('获取方式'), { target: { value: 'webpage' } })
  await act(async () => complete(result))
  expect(apply).not.toHaveBeenCalled()
  click()
  expect(api.mock.calls.at(-1)?.[2].mode).toBe('webpage')
  view.unmount()
  await act(async () => complete(result))
  expect(apply).not.toHaveBeenCalled()
})

test('fetch failure keeps the URL and offers manual completion and retry', async () => {
  api.mockRejectedValueOnce(new Error('network'))
  api.mockResolvedValueOnce({ ...result, status: 'unavailable', fields: {} })
  render(<Harness />)
  fill()
  click()
  await screen.findByText(/暂时无法获取来源/)
  expect((screen.getByLabelText('收录链接') as HTMLInputElement).value).toContain('/status/123')
  click()
  await screen.findByText(/未获取到可用信息/)
})
