import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '@/components/AppLayout'
import { ManagerRoute, ProtectedRoute } from '@/components/ProtectedRoute'
import { LoginPage } from '@/features/auth/LoginPage'
import { SetupAdminPage } from '@/features/auth/SetupAdminPage'
import { DepartmentDetailPage } from '@/features/departments/DepartmentDetailPage'
import { DepartmentsIndex } from '@/features/departments/DepartmentsIndex'
import { StoreDepartmentPage } from '@/features/departments/StoreDepartmentPage'
import { DocketDetailPage } from '@/features/dockets/DocketDetailPage'
import { DocketFormPage } from '@/features/dockets/DocketFormPage'
import { DocketListPage } from '@/features/dockets/DocketListPage'
import { DocketsSection } from '@/features/dockets/DocketsSection'
import { TopSheetPage } from '@/features/dockets/TopSheetPage'
import { RosterPage } from '@/features/rosters/RosterPage'
import { TeamPage } from '@/features/team/TeamPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  // Unlinked on purpose — reached by typing the URL, gated by the setup code.
  { path: '/setup-admin', element: <SetupAdminPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          {
            path: 'dockets',
            element: <DocketsSection />,
            children: [
              { index: true, element: <DocketListPage /> },
              // Static segments are declared before `:id` so they win the match.
              { path: 'top-sheet', element: <TopSheetPage /> },
              { path: 'new', element: <DocketFormPage /> },
              { path: ':id', element: <DocketDetailPage /> },
              { path: ':id/edit', element: <DocketFormPage /> },
            ],
          },
          // Open to everyone, but what you get depends on your role: managers
          // see the group-wide roll-up, staff only their own branch. The API
          // enforces both — these routes just avoid rendering a dead end.
          {
            path: 'departments',
            children: [
              { index: true, element: <DepartmentsIndex /> },
              { path: ':slug', element: <DepartmentDetailPage /> },
              { path: ':slug/:storeSlug', element: <StoreDepartmentPage /> },
            ],
          },
          {
            element: <ManagerRoute />,
            children: [
              { path: 'team', element: <TeamPage /> },
              // Rosters price everybody's week, so they sit behind the same
              // gate as staff administration.
              { path: 'roster', element: <RosterPage /> },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
