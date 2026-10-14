// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { Identity, type Attachment } from './lib/workspace'
import { ImageUploader } from './components/ImageUploader'
import { ReferenceContent } from './components/Attachments'
import { uploadImage } from './lib/upload'
import { readDemo, demoId } from './lib/demo'
import Knowledge from './features/knowledge/Knowledge'
import { CardPicker } from './components/Selectors'
vi.mock('./lib/upload', () => ({ uploadImage: vi.fn() }))
const session = { id: 'user', username: 'alice', role: 'member' as const, is_active: true, csrf_token: 'token' }
const image = { id: '11111111-1111-4111-8111-111111111111', caption: '图注' }
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
function mount(children: React.ReactNode, guest = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Identity value={{ session: guest ? null : session, guest, openLogin: vi.fn(), refresh: async () => {} }}><MemoryRouter>{children}</MemoryRouter></Identity></QueryClientProvider>)
}
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.endsWith('/config') ? json({ max_bytes: 20971520, max_pixels: 40000000, max_edge: 20000, max_images: 10, is_available: true, formats: ['image/png'] }) : new Response('image', { headers: { 'Content-Type': 'image/png' } })))
  URL.createObjectURL = vi.fn(() => 'blob:private-preview'); URL.revokeObjectURL = vi.fn()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks() })

function Uploader() {
  const [images, setImages] = useState<Attachment[]>([]), [busy, setBusy] = useState(false)
  return <><ImageUploader images={images} onChange={setImages} onBusy={setBusy}/><button disabled={busy}>保存测试</button></>
}

test('failed uploads block save and retry preserves the request identity', async () => {
  vi.mocked(uploadImage).mockRejectedValueOnce(new Error('网络中断')).mockResolvedValueOnce(image)
  mount(<Uploader/>); await screen.findByText(/静态JPEG/)
  fireEvent.change(screen.getByLabelText('上传图片'), { target: { files: [new File(['bytes'], 'p.png', { type: 'image/png' })] } })
  await screen.findByText(/网络中断/)
  expect(screen.getByRole('button', { name: '保存测试' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: '重试上传' }))
  await screen.findByLabelText('图注 1')
  expect(vi.mocked(uploadImage).mock.calls[0][1]).toBe(vi.mocked(uploadImage).mock.calls[1][1])
  await waitFor(() => expect(screen.getByRole('button', { name: '保存测试' })).toHaveProperty('disabled', false))
})

test('reference shows material and personal note separately, releases private preview', async () => {
  const card = { id: 'ref', kind: 'reference' as const, title: '外部资料', form: null, body_md: '原作者的摘录', note_md: '我的说明内容', source_author: '原帖作者', attachments: [image], code: 'R', lifecycle: 'active', revision: 1, is_bookmarked: false, processing_state: 'inbox', topics: [], tags: [], topic_ids: [], tag_ids: [] }
  const mounted = mount(<ReferenceContent card={card}/>)
  expect(screen.getByText('原始材料')).toBeTruthy(); expect(screen.getByText('我的说明')).toBeTruthy()
  expect(screen.queryByRole('button', { name: '显示答案' })).toBeNull()
  await waitFor(() => expect(document.querySelector('img')?.getAttribute('src')).toBe('blob:private-preview'))
  mounted.unmount(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-preview')
})

test('guest reference and mixed filters use only demo data and packaged image', async () => {
  mount(<Knowledge/>, true)
  expect(await screen.findByRole('link', { name: '一周借阅记录' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /^资料$/ }))
  await waitFor(() => expect(screen.queryByRole('link', { name: '主动回忆为什么有效？' })).toBeNull())
  await waitFor(() => expect(document.querySelector('img')?.getAttribute('src')).toBe('/demo/reference.svg'))
  expect(fetch).not.toHaveBeenCalled()
  expect(readDemo<{ kind: string }>('/cards/' + demoId(10)).kind).toBe('reference')
})

test('card picker identifies external materials as reference cards', async () => {
  const select = vi.fn()
  mount(<CardPicker onSelect={select}/>, true)
  const button = await screen.findByRole('button', { name: /一周借阅记录.*资料卡/ })
  fireEvent.click(button)
  expect(select.mock.calls[0][0].kind).toBe('reference')
})
