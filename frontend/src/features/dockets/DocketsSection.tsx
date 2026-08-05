import { Outlet } from 'react-router-dom'

import { SubNav } from '@/components/SubNav'

/** Shell for the whole dockets section — every docket screen sits under this. */
export function DocketsSection() {
  return (
    <div>
      <SubNav
        label="Dockets"
        items={[
          { to: '/dockets', label: 'All dockets', end: true },
          { to: '/dockets/new', label: 'New docket' },
          { to: '/dockets/top-sheet', label: 'Top sheet' },
        ]}
      />
      <Outlet />
    </div>
  )
}
