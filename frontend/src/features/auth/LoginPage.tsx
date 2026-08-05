import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field } from '@/components/ui/Field'
import { apiErrorMessage } from '@/lib/apiClient'

import { useAuth } from './useAuth'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not sign in. Check your email and password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__brand">
          <span className="auth__brand-mark">Moriarty Group</span>
          <h1 style={{ marginTop: 'var(--space-3)' }}>Store Tools</h1>
          <p className="u-muted" style={{ fontSize: 'var(--text-sm)' }}>
            Sign in with your work account.
          </p>
        </div>

        <Card>
          <form className="u-stack-sm" onSubmit={handleSubmit} noValidate>
            <Field label="Email">
              <input
                className="input"
                type="email"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>

            <Field label="Password">
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>

            {error && <div className="alert alert--error">{error}</div>}

            <Button type="submit" size="lg" block loading={submitting}>
              Sign in
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
