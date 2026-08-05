import { NavLink } from 'react-router-dom'

export interface SubNavItem {
  to: string
  label: string
  end?: boolean
}

export function SubNav({ items, label }: { items: SubNavItem[]; label: string }) {
  return (
    <nav className="subnav" aria-label={label}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => (isActive ? 'active' : undefined)}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
