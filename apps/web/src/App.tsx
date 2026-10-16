import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Link, NavLink, Navigate, Route, Routes, useNavigate, useLocation, useParams } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, request, useIdentity, type Session } from './lib/workspace'
import { Icon } from './components/Common'
import { registrationRules, usernamePattern, validUsername, validateRegistration, type RegistrationField } from './lib/registration'
import { legacyList } from './lib/card-navigation'
import BuilderLinks from './components/BuilderLinks'
import './App.css'

const Knowledge = lazy(() => import('./features/knowledge/Knowledge'))
const Review = lazy(() => import('./features/knowledge/Review'))
const Memos = lazy(() => import('./features/cards/Memos'))
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
  const navigate = useNavigate(), location = useLocation()
  const [session, setSession] = useState<Session | null>(null), [loading, setLoading] = useState(true)
  const [registration, setRegistration] = useState(false), [open, setOpen] = useState(false), [mode, setMode] = useState('login')
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [confirmation, setConfirmation] = useState(''), [message, setMessage] = useState(''), [pending, setPending] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const submitting = useRef(false)
  const [touched, setTouched] = useState<Partial<Record<RegistrationField, boolean>>>({})
  const registering = mode === 'register'
  const validation = validateRegistration(username, password, confirmation)
  const valid = (registering ? registration && validation.valid : validUsername(username) && password.length >= 1 && password.length <= 128) && !pending
  function fieldFeedback(field: RegistrationField) {
    const error = registering && touched[field] ? validation.errors[field] : ''
    const feedback = error || registrationRules[field]
    return {
      attributes: registering ? { 'aria-describedby': feedback ? `register-${field}-feedback` : undefined, 'aria-invalid': !!error } : {},
      blur: () => { if (registering) setTouched(current => ({ ...current, [field]: true })) },
      hint: registering && feedback && <small className={error ? 'auth-error' : 'auth-rule'} id={`register-${field}-feedback`}>{feedback}</small>,
    }
  }
  const usernameFeedback = fieldFeedback('username'), passwordFeedback = fieldFeedback('password'), confirmationFeedback = fieldFeedback('confirmation')
  function selectMode(next: string) { setTouched({}); setMode(next); setMessage('') }
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
  const openLogin = useCallback(() => { setTouched({}); setMessage(''); setMode('login'); setOpen(true) }, [])
  function protectedPage(element: ReactNode) { return session ? element : <GuestGate/> }
  async function logout() { if (!session) return; try { await request('/auth/logout', 'POST', undefined, session.csrf_token); navigate('/cards'); await clearSession(); setOpen(false) } catch (error) { setMessage((error as Error).message) } }
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!valid || submitting.current) return
    submitting.current = true; setPending(true); setMessage('')
    try { await request('/auth/' + mode, 'POST', { username, password }); setPassword(''); setConfirmation(''); setTouched({}); if (mode === 'register') { setMode('login'); setMessage('注册成功，请登录。') } else { await refresh(); setOpen(false); setUsername(''); navigate('/cards') } }
    catch (error) { setMessage((error as Error).message) } finally { submitting.current = false; setPending(false) }
  }
  const nav = [['/cards', '卡片', 'card'], ['/memos', '备忘', 'pen'], ['/collections', '合集', 'grid'], ['/me', '我的', 'person']]
  return <Identity value={{ session, guest: !loading && !session, openLogin, refresh }}><div className="site-shell"><header className="topbar"><div className="brand-area"><Link className="brand" to="/cards" aria-label="SelfLore 首页"><img className="brand-symbol" src="/favicon.svg" alt=""/><b>SelfLore<span>个人卡片笔记</span></b></Link><div className="header-builder"><BuilderLinks/></div></div><nav className="desktop-nav" aria-label="主导航">{nav.map(([path, label, icon]) => <NavLink key={path} to={path} className={({ isActive }) => isActive || (path === '/cards' && location.pathname.startsWith('/knowledge')) ? 'active' : undefined}><Icon name={icon}/>{label}</NavLink>)}</nav><div className="header-actions"><Link className="button create-action" to="/new">＋ 新建</Link>{session && <button className="account-trigger" onClick={() => navigate('/settings')}><span className="mini-avatar">{session.username[0].toUpperCase()}</span><span>{session.username}</span></button>}</div></header><main className="canvas">{!loading && !session && <div className="demo-banner"><div><b>演示空间 · 只读</b><p>内容与统计均为示例。</p></div><button className="button" onClick={openLogin}>登录 / 注册</button></div>}{loading ? <div className="state" role="status">正在加载…</div> : <Suspense key={session?.id || 'guest'} fallback={<div className="state" role="status">正在加载页面…</div>}><Routes>
    <Route path="/" element={<Navigate to="/cards" replace/>}/><Route path="/cards" element={<Knowledge/>}/><Route path="/cards/:id" element={<DetailPage/>}/><Route path="/memos" element={<Memos/>}/><Route path="/memos/:id" element={<DetailPage/>}/><Route path="/memos/:id/edit" element={protectedPage(<Editor/>)}/><Route path="/knowledge" element={<LegacyList/>}/><Route path="/knowledge/cards/:id" element={<LegacyDetail/>}/><Route path="/knowledge/references/:id" element={<LegacyDetail/>}/><Route path="/knowledge/review" element={protectedPage(<Review/>)}/><Route path="/opinions" element={<LegacyList opinion/>}/><Route path="/collections" element={<Collections/>}/><Route path="/collections/new" element={protectedPage(<CollectionEditor/>)}/><Route path="/collections/:id/edit" element={protectedPage(<CollectionEditor/>)}/><Route path="/collections/:id" element={<Collections/>}/><Route path="/me" element={<Profile/>}/><Route path="/new" element={protectedPage(<Editor/>)}/><Route path="/cards/:id/edit" element={protectedPage(<Editor/>)}/><Route path="/settings" element={protectedPage(<Account logout={logout}/>)}/><Route path="/admin/users" element={protectedPage(<AdminUsers/>)}/><Route path="/trash" element={protectedPage(<Trash/>)}/><Route path="*" element={<div className="state"><h1>页面不存在</h1><Link to="/cards">返回卡片库</Link></div>}/>
    </Routes></Suspense>}</main><nav className="mobile-nav" aria-label="移动端导航">{[...nav.slice(0, 2), ['/new', '新建', ''], ...nav.slice(2)].map(([path, label, icon]) => <NavLink key={path} to={path} className={({ isActive }) => path === '/new' ? 'mobile-create' : isActive || (path === '/cards' && location.pathname.startsWith('/knowledge')) ? 'active' : undefined}>{path === '/new' ? <span className="mobile-create-symbol" aria-hidden="true">＋</span> : <Icon name={icon}/>}<span>{label}</span></NavLink>)}</nav><footer className="site-footer"><span>SelfLore</span><BuilderLinks/></footer></div>
    <dialog className="auth-dialog" ref={dialog} aria-labelledby="auth-title" onClose={() => { setTouched({}); setOpen(false); setPassword(''); setConfirmation('') }} onClick={e => { if (e.target === e.currentTarget) setOpen(false) }}>
      <div className="auth-head"><button aria-label="关闭登录窗口" onClick={() => setOpen(false)}>×</button></div>
      <h2 id="auth-title">{registering ? '注册' : '登录'}</h2>
      <div className="auth-tabs" role="tablist" aria-label="账号操作"><button role="tab" aria-selected={mode === 'login'} onClick={() => selectMode('login')}>登录</button>{registration && <button role="tab" aria-selected={registering} onClick={() => selectMode('register')}>注册</button>}</div>
      <form onSubmit={e => void submit(e)}>
        <div className="auth-field"><label>用户名<input autoFocus autoComplete="username" pattern={usernamePattern} maxLength={32} required value={username} onChange={e => setUsername(e.target.value)} onBlur={usernameFeedback.blur} {...usernameFeedback.attributes}/></label>{usernameFeedback.hint}</div>
        <div className="auth-field"><label>密码<input type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 8 : 1} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} onBlur={passwordFeedback.blur} {...passwordFeedback.attributes}/></label>{passwordFeedback.hint}</div>
        {registering && <div className="auth-field"><label>确认密码<input type="password" autoComplete="new-password" required value={confirmation} onChange={e => setConfirmation(e.target.value)} onBlur={confirmationFeedback.blur} {...confirmationFeedback.attributes}/></label>{confirmationFeedback.hint}</div>}
        <p role="status">{pending ? '正在提交，请稍候…' : message}</p>
        <button className="primary" disabled={!valid}>{pending ? '请稍候…' : registering ? '注册' : '登录'}</button>
      </form>
    </dialog></Identity>
}

function LegacyList({ opinion = false }: { opinion?: boolean }) { const location = useLocation(); return <Navigate replace to={legacyList(location.search, opinion)}/> }
function LegacyDetail() { const { id } = useParams(); const location = useLocation(); return <Navigate replace to={'/cards/' + id + location.search}/> }

function GuestGate() {
  const { openLogin } = useIdentity()
  useEffect(() => { openLogin() }, [openLogin])
  return <section className="state panel"><Icon name="person"/><h1>请先登录</h1><p>新建、编辑、收藏和复习评分需要登录。</p><button className="button primary" onClick={openLogin}>登录或注册</button><Link className="back-link" to="/knowledge">← 返回演示知识库</Link></section>
}
