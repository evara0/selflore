import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { useIdentity, type Session } from '../lib/workspace'
import { Icon } from '../components/Common'
import { legacyList } from '../lib/card-navigation'

const Cards = lazy(() => import('../features/cards/Cards'))
const Review = lazy(() => import('../features/knowledge/Review'))
const Memos = lazy(() => import('../features/cards/Memos'))
const Collections = lazy(() => import('../features/collections/Collections'))
const Profile = lazy(() => import('../features/profile/Profile'))
const Editor = lazy(() => import('../features/cards/Editor'))
const CollectionEditor = lazy(() => import('../features/collections/CollectionEditor'))
const DetailPage = lazy(() => import('../features/cards/Detail'))
const Account = lazy(() => import('../features/account/Account'))
const AdminUsers = lazy(() =>
  import('../features/account/Account').then((m) => ({ default: m.AdminUsers })),
)
const Trash = lazy(() => import('../features/account/Account').then((m) => ({ default: m.Trash })))

type Props = { session: Session | null; logout: () => Promise<void> }
export default function WorkspaceRoutes({ session, logout }: Props) {
  function protectedPage(element: ReactNode) {
    return session ? element : <GuestGate />
  }
  return (
    <Suspense
      key={session?.id || 'guest'}
      fallback={
        <div className="state" role="status">
          正在加载页面…
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<Navigate to="/cards" replace />} />
        <Route path="/cards" element={<Cards />} />
        <Route path="/cards/:id" element={<DetailPage />} />
        <Route path="/memos" element={<Memos />} />
        <Route path="/memos/:id" element={<DetailPage />} />
        <Route path="/memos/:id/edit" element={protectedPage(<Editor />)} />
        <Route path="/knowledge" element={<LegacyList />} />
        <Route path="/knowledge/cards/:id" element={<LegacyDetail />} />
        <Route path="/knowledge/references/:id" element={<LegacyDetail />} />
        <Route path="/knowledge/review" element={protectedPage(<Review />)} />
        <Route path="/opinions" element={<LegacyList opinion />} />
        <Route path="/collections" element={<Collections />} />
        <Route path="/collections/new" element={protectedPage(<CollectionEditor />)} />
        <Route path="/collections/:id/edit" element={protectedPage(<CollectionEditor />)} />
        <Route path="/collections/:id" element={<Collections />} />
        <Route path="/me" element={<Profile />} />
        <Route path="/new" element={protectedPage(<Editor />)} />
        <Route path="/cards/:id/edit" element={protectedPage(<Editor />)} />
        <Route path="/settings" element={protectedPage(<Account logout={logout} />)} />
        <Route path="/admin/users" element={protectedPage(<AdminUsers />)} />
        <Route path="/trash" element={protectedPage(<Trash />)} />
        <Route
          path="*"
          element={
            <div className="state">
              <h1>页面不存在</h1>
              <Link to="/cards">返回卡片库</Link>
            </div>
          }
        />
      </Routes>
    </Suspense>
  )
}

function LegacyList({ opinion = false }: { opinion?: boolean }) {
  const location = useLocation()
  return <Navigate replace to={legacyList(location.search, opinion)} />
}
function LegacyDetail() {
  const { id } = useParams()
  const location = useLocation()
  return <Navigate replace to={'/cards/' + id + location.search} />
}

function GuestGate() {
  const { openLogin } = useIdentity()
  useEffect(() => {
    openLogin()
  }, [openLogin])
  return (
    <section className="state panel">
      <Icon name="person" />
      <h1>请先登录</h1>
      <p>新建、编辑、收藏和复习评分需要登录。</p>
      <button className="button primary" onClick={openLogin}>
        登录或注册
      </button>
      <Link className="back-link" to="/knowledge">
        ← 返回演示知识库
      </Link>
    </section>
  )
}
