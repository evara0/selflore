import { NavLink } from 'react-router-dom'

export default function CreateNavigation() {
  return (
    <nav className="create-methods segmented" aria-label="新建方式">
      <NavLink to="/new" end className={({ isActive }) => (isActive ? 'selected' : '')}>
        手动新建
      </NavLink>
      <NavLink to="/import" className={({ isActive }) => (isActive ? 'selected' : '')}>
        JSON 导入
      </NavLink>
    </nav>
  )
}
