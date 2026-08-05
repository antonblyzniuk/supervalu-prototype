import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'

export function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <Card>
      <EmptyState
        icon="🧭"
        title="Page not found"
        description="That link does not point anywhere in the tool."
        action={<Button onClick={() => navigate('/')}>Go to dashboard</Button>}
      />
    </Card>
  )
}
