import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { createBrowserRouter, RouterProvider, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, request, type Session } from './lib/workspace'
import {
  registrationRules,
  validUsername,
  validateRegistration,
  type RegistrationField,
} from './lib/registration'
import WorkspaceLayout from './app/WorkspaceLayout'
import WorkspaceRoutes from './app/WorkspaceRoutes'
import AuthDialog from './features/auth/AuthDialog'
import './App.css'

export default function App() {
  const [cache] = useState(() => new QueryClient())
  const [router] = useState(() =>
    createBrowserRouter([{ path: '*', element: <Workspace cache={cache} /> }]),
  )
  return (
    <QueryClientProvider client={cache}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
function Workspace({ cache }: { cache: QueryClient }) {
  const navigate = useNavigate()
  const [session, setSession] = useState<Session | null>(null),
    [loading, setLoading] = useState(true)
  const [registration, setRegistration] = useState(false),
    [open, setOpen] = useState(false),
    [mode, setMode] = useState('login')
  const [username, setUsername] = useState(''),
    [password, setPassword] = useState(''),
    [confirmation, setConfirmation] = useState(''),
    [message, setMessage] = useState(''),
    [pending, setPending] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const submitting = useRef(false)
  const [touched, setTouched] = useState<Partial<Record<RegistrationField, boolean>>>({})
  const registering = mode === 'register'
  const validation = validateRegistration(username, password, confirmation)
  const valid =
    (registering
      ? registration && validation.valid
      : validUsername(username) && password.length >= 1 && password.length <= 128) && !pending
  function fieldFeedback(field: RegistrationField) {
    const error = registering && touched[field] ? validation.errors[field] : ''
    const feedback = error || registrationRules[field]
    return {
      attributes: registering
        ? {
            'aria-describedby': feedback ? `register-${field}-feedback` : undefined,
            'aria-invalid': !!error,
          }
        : {},
      blur: () => {
        if (registering) setTouched((current) => ({ ...current, [field]: true }))
      },
      hint: registering && feedback && (
        <small className={error ? 'auth-error' : 'auth-rule'} id={`register-${field}-feedback`}>
          {feedback}
        </small>
      ),
    }
  }
  const usernameFeedback = fieldFeedback('username'),
    passwordFeedback = fieldFeedback('password'),
    confirmationFeedback = fieldFeedback('confirmation')
  function selectMode(next: string) {
    setTouched({})
    setMode(next)
    setMessage('')
  }
  const clearSession = useCallback(async () => {
    await cache.cancelQueries()
    cache.clear()
    setSession(null)
  }, [cache])
  const refresh = useCallback(async () => {
    try {
      const next = await request<Session>('/auth/me')
      await cache.cancelQueries()
      cache.clear()
      setSession(next)
    } catch {
      await clearSession()
    }
  }, [cache, clearSession])
  useEffect(() => {
    const controller = new AbortController()
    request<Session>('/auth/me', 'GET', undefined, undefined, controller.signal)
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setLoading(false))
    request<{ registration_enabled: boolean }>(
      '/auth/config',
      'GET',
      undefined,
      undefined,
      controller.signal,
    )
      .then((r) => setRegistration(r.registration_enabled))
      .catch(() => {})
    return () => controller.abort()
  }, [])
  useEffect(() => {
    const expired = () => {
      void clearSession()
      setMessage('会话已过期，请重新登录。')
    }
    window.addEventListener('session-expired', expired)
    return () => window.removeEventListener('session-expired', expired)
  }, [clearSession])
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal()
    if (!open && dialog.current?.open) dialog.current.close()
  }, [open])
  const openLogin = useCallback(() => {
    setTouched({})
    setMessage('')
    setMode('login')
    setOpen(true)
  }, [])
  async function logout() {
    if (!session) return
    try {
      await request('/auth/logout', 'POST', undefined, session.csrf_token)
      navigate('/cards')
      await clearSession()
      setOpen(false)
    } catch (error) {
      setMessage((error as Error).message)
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!valid || submitting.current) return
    submitting.current = true
    setPending(true)
    setMessage('')
    try {
      await request('/auth/' + mode, 'POST', { username, password })
      setPassword('')
      setConfirmation('')
      setTouched({})
      if (mode === 'register') {
        setMode('login')
        setMessage('注册成功，请登录。')
      } else {
        await refresh()
        setOpen(false)
        setUsername('')
        navigate('/cards')
      }
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      submitting.current = false
      setPending(false)
    }
  }
  return (
    <Identity value={{ session, guest: !loading && !session, openLogin, refresh }}>
      <WorkspaceLayout session={session} loading={loading} openLogin={openLogin}>
        <WorkspaceRoutes session={session} logout={logout} />
      </WorkspaceLayout>
      <AuthDialog
        dialog={dialog}
        registering={registering}
        registration={registration}
        mode={mode}
        username={username}
        password={password}
        confirmation={confirmation}
        message={message}
        pending={pending}
        valid={valid}
        usernameFeedback={usernameFeedback}
        passwordFeedback={passwordFeedback}
        confirmationFeedback={confirmationFeedback}
        setUsername={setUsername}
        setPassword={setPassword}
        setConfirmation={setConfirmation}
        selectMode={selectMode}
        setOpen={setOpen}
        submit={submit}
        onClose={() => {
          setTouched({})
          setOpen(false)
          setPassword('')
          setConfirmation('')
        }}
      />
    </Identity>
  )
}
