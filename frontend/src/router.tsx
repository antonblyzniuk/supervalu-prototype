import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '@/components/AppLayout'
import { ManagerRoute, ProtectedRoute } from '@/components/ProtectedRoute'
import { LoginPage } from '@/features/auth/LoginPage'
import { SetupAdminPage } from '@/features/auth/SetupAdminPage'
import { DocketDetailPage } from '@/features/dockets/DocketDetailPage'
import { DocketFormPage } from '@/features/dockets/DocketFormPage'
import { DocketListPage } from '@/features/dockets/DocketListPage'
import { DocketsSection } from '@/features/dockets/DocketsSection'
import { TopSheetPage } from '@/features/dockets/TopSheetPage'
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
          {
            element: <ManagerRoute />,
            children: [{ path: 'team', element: <TeamPage /> }],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
