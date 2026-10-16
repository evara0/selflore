import type { ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { Session } from '../lib/workspace'
import { Icon } from '../components/Common'
import BuilderLinks from '../components/BuilderLinks'

type Props = {
  session: Session | null
  loading: boolean
  openLogin: () => void
  children: ReactNode
}
export default function WorkspaceLayout({ session, loading, openLogin, children }: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const nav = [
    ['/cards', '卡片', 'card'],
    ['/memos', '备忘', 'pen'],
    ['/collections', '合集', 'grid'],
    ['/me', '我的', 'person'],
  ]
  return (
    <div className="site-shell">
      <header className="topbar">
        <div className="brand-area">
          <Link className="brand" to="/cards" aria-label="SelfLore 首页">
            <img className="brand-symbol" src="/favicon.svg" alt="" />
            <b>
              SelfLore<span>个人卡片笔记</span>
            </b>
          </Link>
          <div className="header-builder">
            <BuilderLinks />
          </div>
        </div>
        <nav className="desktop-nav" aria-label="主导航">
          {nav.map(([path, label, icon]) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                isActive || (path === '/cards' && location.pathname.startsWith('/knowledge'))
                  ? 'active'
                  : undefined
              }
            >
              <Icon name={icon} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="button create-action" to="/new">
            ＋ 新建
          </Link>
          {session && (
            <button className="account-trigger" onClick={() => navigate('/settings')}>
              <span className="mini-avatar">{session.username[0].toUpperCase()}</span>
              <span>{session.username}</span>
            </button>
          )}
        </div>
      </header>
      <main className="canvas">
        {!loading && !session && (
          <div className="demo-banner">
            <div>
              <b>演示空间 · 只读</b>
              <p>内容与统计均为示例。</p>
            </div>
            <button className="button" onClick={openLogin}>
              登录 / 注册
            </button>
          </div>
        )}
        {loading ? (
          <div className="state" role="status">
            正在加载…
          </div>
        ) : (
          children
        )}
      </main>
      <nav className="mobile-nav" aria-label="移动端导航">
        {[...nav.slice(0, 2), ['/new', '新建', ''], ...nav.slice(2)].map(([path, label, icon]) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              path === '/new'
                ? 'mobile-create'
                : isActive || (path === '/cards' && location.pathname.startsWith('/knowledge'))
                  ? 'active'
                  : undefined
            }
          >
            {path === '/new' ? (
              <span className="mobile-create-symbol" aria-hidden="true">
                ＋
              </span>
            ) : (
              <Icon name={icon} />
            )}
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <footer className="site-footer">
        <span>SelfLore</span>
        <BuilderLinks />
      </footer>
    </div>
  )
}
