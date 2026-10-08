import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Link, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, request, useIdentity, type Session } from './lib/workspace'
import { Icon } from './components/Common'
import './App.css'

const Knowledge = lazy(() => import('./features/knowledge/Knowledge'))
const Review = lazy(() => import('./features/knowledge/Review'))
const Opinions = lazy(() => import('./features/opinions/Opinions'))
const Collections = lazy(() => import('./features/collections/Collections'))
const Profile = lazy(() => import('./features/profile/Profile'))
const Editor = lazy(() => import('./features/cards/Editor'))
const CollectionEditor = lazy(() => import('./features/cards/Editor').then(m => ({ default: m.CollectionEditor })))
const DetailPage = lazy(() => import('./features/cards/Detail'))
const Account = lazy(() => import('./features/account/Account'))
const AdminUsers = lazy(() => import('./features/account/Account').then(m => ({ default: m.AdminUsers })))
const Trash = lazy(() => import('./features/account/Account').then(m => ({ default: m.Trash })))

export default function App() {
  const [cache] = useState(() => new QueryClient())
  const [router] = useState(() => createBrowserRouter([{ path: '*', element: <Workspace cache={cache}/> }]))
  return <QueryClientProvider client={cache}><RouterProvider router={router}/></QueryClientProvider>
}
function Workspace({ cache }: { cache: QueryClient }) {
  const navigate = useNavigate()
  const [session, setSession] = useState<Session | null>(null), [loading, setLoading] = useState(true)
  const [registration, setRegistration] = useState(false), [open, setOpen] = useState(false), [mode, setMode] = useState('login')
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [confirmation, setConfirmation] = useState(''), [message, setMessage] = useState(''), [pending, setPending] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const clearSession = useCallback(async () => { await cache.cancelQueries(); cache.clear(); setSession(null) }, [cache])
  const refresh = useCallback(async () => { try { const next = await request<Session>('/auth/me'); await cache.cancelQueries(); cache.clear(); setSession(next) } catch { await clearSession() } }, [cache, clearSession])
  useEffect(() => {
    const controller = new AbortController()
    request<Session>('/auth/me', 'GET', undefined, undefined, controller.signal).then(setSession).catch(() => setSession(null)).finally(() => setLoading(false))
    request<{ registration_enabled: boolean }>('/auth/config', 'GET', undefined, undefined, controller.signal).then(r => setRegistration(r.registration_enabled)).catch(() => {})
    return () => controller.abort()
  }, [])
  useEffect(() => { const expired = () => { void clearSession(); setMessage('会话已过期，请重新登录。') }; window.addEventListener('session-expired', expired); return () => window.removeEventListener('session-expired', expired) }, [clearSession])
  useEffect(() => { if (open && !dialog.current?.open) dialog.current?.showModal(); if (!open && dialog.current?.open) dialog.current.close() }, [open])
  const openLogin = useCallback(() => { setMessage(''); setMode('login'); setOpen(true) }, [])
  function protectedPage(element: ReactNode) { return session ? element : <GuestGate/> }
  async function logout() { if (!session) return; try { await request('/auth/logout', 'POST', undefined, session.csrf_token); await clearSession(); navigate('/knowledge') } catch (error) { setMessage((error as Error).message) } }
  async function submit(e: FormEvent) {
    e.preventDefault(); setPending(true); setMessage('')
    try { await request('/auth/' + mode, 'POST', { username, password }); setPassword(''); setConfirmation(''); if (mode === 'register') { setMode('login'); setMessage('注册成功，请登录。') } else { await refresh(); setOpen(false); setUsername(''); navigate('/knowledge') } }
    catch (error) { setMessage((error as Error).message) } finally { setPending(false) }
  }
  const valid = /^[a-z][a-z0-9_-]{2,31}$/i.test(username) && password.length >= (mode === 'register' ? 12 : 1) && password.length <= 128 && (mode === 'login' || confirmation === password && registration) && !pending
  const nav = [['/knowledge', '知识', 'book'], ['/opinions', '观点', 'link'], ['/collections', '合集', 'grid'], ['/me', '我的', 'person']]
  return <Identity value={{ session, guest: !loading && !session, openLogin, refresh }}><div className="site-shell"><header className="topbar"><Link className="brand" to="/knowledge" aria-label="SelfLore 首页"><span className="brand-symbol">✳</span><b>SelfLore<span>个人知识与思考</span></b></Link><nav className="desktop-nav" aria-label="主导航">{nav.map(([path, label, icon]) => <NavLink key={path} to={path}><Icon name={icon}/>{label}</NavLink>)}</nav><div className="header-actions"><Link className="button create-action" to="/new">＋ 新建</Link><button className="account-trigger" onClick={() => session ? navigate('/settings') : openLogin()}>{session ? <><span className="mini-avatar">{session.username[0].toUpperCase()}</span><span>{session.username}</span></> : '登录'}</button></div></header><main className="canvas">{!loading && !session && <div className="demo-banner"><div><b>演示空间 · 只读</b><p>自由浏览、查看关联和翻阅卡片。资料、数量与学习足迹均为示例。</p></div><button className="button" onClick={openLogin}>进入自己的空间 →</button></div>}{loading ? <div className="state" role="status">正在进入你的空间…</div> : <Suspense key={session?.id || 'guest'} fallback={<div className="state" role="status">正在加载页面…</div>}><Routes>
    <Route path="/" element={<Navigate to="/knowledge" replace/>}/><Route path="/knowledge" element={<Knowledge/>}/><Route path="/knowledge/cards/:id" element={<DetailPage/>}/><Route path="/knowledge/review" element={protectedPage(<Review/>)}/><Route path="/opinions" element={<Opinions/>}/><Route path="/collections" element={<Collections/>}/><Route path="/collections/new" element={protectedPage(<CollectionEditor/>)}/><Route path="/collections/:id/edit" element={protectedPage(<CollectionEditor/>)}/><Route path="/collections/:id" element={<Collections/>}/><Route path="/me" element={<Profile/>}/><Route path="/new" element={protectedPage(<Editor/>)}/><Route path="/cards/:id/edit" element={protectedPage(<Editor/>)}/><Route path="/settings" element={protectedPage(<Account logout={logout}/>)}/><Route path="/admin/users" element={protectedPage(<AdminUsers/>)}/><Route path="/trash" element={protectedPage(<Trash/>)}/><Route path="*" element={<div className="state"><h1>页面不存在</h1><Link to="/knowledge">返回知识库</Link></div>}/>
    </Routes></Suspense>}</main><nav className="mobile-nav" aria-label="移动端导航">{[...nav.slice(0, 2), ['/new', '新建', ''], ...nav.slice(2)].map(([path, label, icon]) => <NavLink key={path} to={path} className={path === '/new' ? 'mobile-create' : undefined}>{path === '/new' ? <span className="mobile-create-symbol" aria-hidden="true">＋</span> : <Icon name={icon}/>}<span>{label}</span></NavLink>)}</nav><footer className="site-footer"><span>SelfLore · 让知识和思考，慢慢长成自己的样子。</span><span>记录 · 连接 · 回忆</span></footer></div>
    <dialog className="auth-dialog" ref={dialog} aria-labelledby="auth-title" onClose={() => { setOpen(false); setPassword(''); setConfirmation('') }} onClick={e => { if (e.target === e.currentTarget) setOpen(false) }}><div className="auth-head"><span className="eyebrow">SELFLORE ACCOUNT</span><button aria-label="关闭登录窗口" onClick={() => setOpen(false)}>×</button></div><h2 id="auth-title">继续前先进入自己的空间</h2><p className="muted">登录后，记录会进入你自己的独立空间。</p><div className="auth-tabs" role="tablist" aria-label="账号操作"><button role="tab" aria-selected={mode === 'login'} onClick={() => { setMode('login'); setMessage('') }}>登录</button>{registration && <button role="tab" aria-selected={mode === 'register'} onClick={() => { setMode('register'); setMessage('') }}>注册</button>}</div><form onSubmit={e => void submit(e)}><label>用户名<input autoFocus autoComplete="username" pattern="[A-Za-z][A-Za-z0-9_-]{2,31}" maxLength={32} required value={username} onChange={e => setUsername(e.target.value)}/></label><label>密码<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 12 : 1} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)}/></label>{mode === 'register' && <label>确认密码<input type="password" autoComplete="new-password" required value={confirmation} onChange={e => setConfirmation(e.target.value)}/></label>}<p role="status">{message}</p><button className="primary" disabled={!valid}>{pending ? '请稍候…' : mode === 'login' ? '登录' : '注册'}</button></form></dialog></Identity>
}

function GuestGate() {
  const { openLogin } = useIdentity()
  useEffect(() => { openLogin() }, [openLogin])
  return <section className="state panel"><Icon name="person"/><h1>在自己的空间继续</h1><p>演示空间可以浏览、翻阅和揭示答案。新建、编辑、保存与复习评分需要登录或注册。</p><button className="button primary" onClick={openLogin}>登录或注册</button><Link className="back-link" to="/knowledge">← 返回演示知识库</Link></section>
}
