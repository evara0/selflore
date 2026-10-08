import { createContext, useContext } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { DEMO_CACHE_KEY, readDemo } from './demo'

export type Session = { id: string; username: string; role: 'member' | 'admin'; is_active: boolean; csrf_token: string }
export type Label = { id: string; name: string; card_count?: number; kind?: string }
export type Card = { id: string; title: string; code: string; kind: 'knowledge' | 'opinion'; form: 'qa' | 'cloze' | null; question_md?: string; answer_md?: string; body_md?: string; excerpt?: string; lifecycle: string; revision: number; is_bookmarked: boolean; processing_state: string; source_title?: string; source_url?: string; source_locator?: string; tags: Label[]; topics: Label[]; tag_ids: string[]; topic_ids: string[]; link_count?: number; backlink_count?: number; updated_at?: string }
export type Collection = { id: string; title: string; description_md: string; cover_style: string; cover_color: string; is_favorite: boolean; is_pinned: boolean; revision: number; lifecycle: string; total_items: number; available_items: number; knowledge_count: number; opinion_count: number }
export type Page<T> = { items: T[]; total: number; limit: number; offset: number }
export type Profile = { display_name: string; username: string; bio: string; avatar_color: string; interests: string[]; timezone: string; revision: number; daily_new_limit: number; daily_review_goal: number }
export type ReviewSummary = { due_units: number; new_units: number; today_completed: number; mastered_cards: number; daily_review_goal: number }
export type Unit = { id: string; card: Card; question: string; answer: string; state: string; state_version: number; cloze_index: number; due_at: string }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
export async function request<T>(path: string, method = 'GET', body?: unknown, token?: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { method, credentials: 'same-origin', signal,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { 'X-CSRF-Token': token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const detail = payload.detail
    const message = Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join('；') : typeof detail === 'object' ? detail?.message : detail
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('session-expired'))
    throw new ApiError(message || `请求失败 (${response.status})`, response.status)
  }
  return response.status === 204 ? undefined as T : response.json()
}

export const Identity = createContext<{ session: Session | null; guest?: boolean; openLogin: () => void; refresh: () => Promise<void> }>({ session: null, openLogin: () => {}, refresh: async () => {} })
export function useIdentity() { return useContext(Identity) }
export function useApi() {
  const { session, guest, openLogin } = useIdentity()
  return async <T,>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> => {
    if (guest && !session) {
      if (method !== 'GET') { openLogin(); throw new ApiError('演示空间为只读，请登录或注册后保存到自己的空间。', 401) }
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return readDemo<T>(path)
    }
    return request<T>(path, method, body, session?.csrf_token, signal)
  }
}
export function useData<T>(path: string, enabled = true) {
  const { session, guest } = useIdentity()
  const api = useApi()
  return useQuery<T, Error>({ queryKey: [session?.id || (guest ? DEMO_CACHE_KEY : undefined), path], queryFn: ({ signal }) => api<T>(path, 'GET', undefined, signal), enabled: (!!session || !!guest) && enabled, retry: false, staleTime: 10000 })
}
export function useRefresh() {
  const cache = useQueryClient()
  return () => cache.invalidateQueries()
}
export function params(values: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') query.set(key, String(value)) })
  return query.toString()
}
export function cardUrl(card: { id: string; kind: string }) { return card.kind === 'knowledge' ? `/knowledge/cards/${card.id}` : `/opinions?card=${card.id}` }
export function showDate(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '' }
export function clozeText(text: string, reveal: boolean) {
  return text.replace(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`]*`)|(\{\{c\d+::([^{}]+)\}\})/g, (_whole, code, _cloze, content) => code || (reveal ? content.split('::')[0] : `【${content.split('::')[1] || '…'}】`))
}
