import type { FormEvent, InputHTMLAttributes, ReactNode, RefObject } from 'react'
import { usernamePattern } from '../../lib/registration'

type FieldFeedback = {
  attributes: InputHTMLAttributes<HTMLInputElement>
  blur: () => void
  hint: ReactNode
}
type Props = {
  dialog: RefObject<HTMLDialogElement | null>
  registering: boolean
  registration: boolean
  mode: string
  username: string
  password: string
  confirmation: string
  message: string
  pending: boolean
  valid: boolean
  usernameFeedback: FieldFeedback
  passwordFeedback: FieldFeedback
  confirmationFeedback: FieldFeedback
  setUsername: (value: string) => void
  setPassword: (value: string) => void
  setConfirmation: (value: string) => void
  selectMode: (mode: string) => void
  setOpen: (open: boolean) => void
  submit: (event: FormEvent) => Promise<void>
  onClose: () => void
}
export default function AuthDialog({
  dialog,
  registering,
  registration,
  mode,
  username,
  password,
  confirmation,
  message,
  pending,
  valid,
  usernameFeedback,
  passwordFeedback,
  confirmationFeedback,
  setUsername,
  setPassword,
  setConfirmation,
  selectMode,
  setOpen,
  submit,
  onClose,
}: Props) {
  return (
    <dialog
      className="auth-dialog"
      ref={dialog}
      aria-labelledby="auth-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) setOpen(false)
      }}
    >
      <div className="auth-head">
        <button aria-label="关闭登录窗口" onClick={() => setOpen(false)}>
          ×
        </button>
      </div>
      <h2 id="auth-title">{registering ? '注册' : '登录'}</h2>
      <div className="auth-tabs" role="tablist" aria-label="账号操作">
        <button role="tab" aria-selected={mode === 'login'} onClick={() => selectMode('login')}>
          登录
        </button>
        {registration && (
          <button role="tab" aria-selected={registering} onClick={() => selectMode('register')}>
            注册
          </button>
        )}
      </div>
      <form onSubmit={(e) => void submit(e)}>
        <div className="auth-field">
          <label>
            用户名
            <input
              autoFocus
              autoComplete="username"
              pattern={usernamePattern}
              maxLength={32}
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onBlur={usernameFeedback.blur}
              {...usernameFeedback.attributes}
            />
          </label>
          {usernameFeedback.hint}
        </div>
        <div className="auth-field">
          <label>
            密码
            <input
              type="password"
              autoComplete={registering ? 'new-password' : 'current-password'}
              minLength={registering ? 8 : 1}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={passwordFeedback.blur}
              {...passwordFeedback.attributes}
            />
          </label>
          {passwordFeedback.hint}
        </div>
        {registering && (
          <div className="auth-field">
            <label>
              确认密码
              <input
                type="password"
                autoComplete="new-password"
                required
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                onBlur={confirmationFeedback.blur}
                {...confirmationFeedback.attributes}
              />
            </label>
            {confirmationFeedback.hint}
          </div>
        )}
        <p role="status">{pending ? '正在提交，请稍候…' : message}</p>
        <button className="primary" disabled={!valid}>
          {pending ? '请稍候…' : registering ? '注册' : '登录'}
        </button>
      </form>
    </dialog>
  )
}
