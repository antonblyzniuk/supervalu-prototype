import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import axios from 'axios'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field } from '@/components/ui/Field'
import { apiErrorMessage } from '@/lib/apiClient'

import { bootstrapAdmin } from './api'
import { useAuth } from './useAuth'

/**
 * Creates the first admin account without needing shell access.
 *
 * Gated by a setup code the backend reads from ADMIN_BOOTSTRAP_CODE. The route
 * is deliberately not linked from anywhere — you reach it by typing the URL.
 */
export function SetupAdminPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    secret_code: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [disabled, setDisabled] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  const patch = (changes: Partial<typeof form>) => setForm({ ...form, ...changes })

  /** DRF returns {field: [messages]}; flatten it onto the matching inputs. */
  function applyFieldErrors(error: unknown): boolean {
    if (!axios.isAxiosError(error) || !error.response) return false
    const data = error.response.data as Record<string, unknown> | undefined
    if (!data || typeof data !== 'object') return false

    const mapped: Record<string, string> = {}
    for (const [key, value] of Object.entries(data)) {
      if (key in form) mapped[key] = Array.isArray(value) ? String(value[0]) : String(value)
    }
    setErrors(mapped)
    return Object.keys(mapped).length > 0
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setErrors({})
    setFormError(null)
    setSubmitting(true)

    try {
      await bootstrapAdmin({
        secret_code: form.secret_code,
        email: form.email.trim(),
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      })
      // Straight in — they have just proved they hold the setup code.
      await login(form.email.trim(), form.password)
      navigate('/', { replace: true })
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setDisabled(true)
      } else if (axios.isAxiosError(error) && error.response?.status === 429) {
        setFormError('Too many attempts. Wait a while before trying again.')
      } else if (!applyFieldErrors(error)) {
        setFormError(apiErrorMessage(error, 'Could not create the account.'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__brand">
          <span className="auth__brand-mark">Moriarty Group</span>
          <h1 style={{ marginTop: 'var(--space-3)' }}>Create an admin</h1>
          <p className="u-muted" style={{ fontSize: 'var(--text-sm)' }}>
            One-time setup. Needs the setup code from the server configuration.
          </p>
        </div>

        <Card>
          {disabled ? (
            <div className="u-stack-sm">
              <div className="alert alert--info">
                Admin setup is switched off on this server. It is enabled by setting
                <code> ADMIN_BOOTSTRAP_CODE</code> in the backend environment.
              </div>
              <Link to="/login">
                <Button block variant="secondary">
                  Back to sign in
                </Button>
              </Link>
            </div>
          ) : (
            <form className="u-stack-sm" onSubmit={handleSubmit} noValidate>
              <Field
                label="Setup code"
                required
                error={errors.secret_code}
                hint="From the backend's ADMIN_BOOTSTRAP_CODE variable."
              >
                <input
                  className="input"
                  type="password"
                  autoComplete="off"
                  value={form.secret_code}
                  onChange={(event) => patch({ secret_code: event.target.value })}
                  required
                />
              </Field>

              <div className="form-grid form-grid--2">
                <Field label="First name">
                  <input
                    className="input"
                    value={form.first_name}
                    onChange={(event) => patch({ first_name: event.target.value })}
                  />
                </Field>
                <Field label="Last name">
                  <input
                    className="input"
                    value={form.last_name}
                    onChange={(event) => patch({ last_name: event.target.value })}
                  />
                </Field>
              </div>

              <Field label="Work email" required error={errors.email}>
                <input
                  className="input"
                  type="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  autoComplete="username"
                  value={form.email}
                  onChange={(event) => patch({ email: event.target.value })}
                  required
                />
              </Field>

              <Field
                label="Password"
                required
                error={errors.password}
                hint="At least 8 characters, and not a common password."
              >
                <input
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(event) => patch({ password: event.target.value })}
                  required
                />
              </Field>

              {formError && <div className="alert alert--error">{formError}</div>}

              <Button type="submit" size="lg" block loading={submitting}>
                Create admin account
              </Button>

              <p className="u-subtle" style={{ fontSize: 'var(--text-xs)', textAlign: 'center' }}>
                Already have an account? <Link to="/login">Sign in</Link>
              </p>
            </form>
          )}
        </Card>
      </div>
    </div>
  )
}
