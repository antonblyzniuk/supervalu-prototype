import { useId, type ReactElement, type ReactNode, cloneElement } from 'react'

interface FieldProps {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  required?: boolean
  className?: string
  /** A single form control; it receives the generated id and aria wiring. */
  children: ReactElement<{ id?: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string }>
}

export function Field({ label, hint, error, required, className = '', children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined

  return (
    <div className={`field ${className}`}>
      <label className="field__label" htmlFor={id}>
        {label}
        {required && (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {cloneElement(children, {
        id,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy,
      })}
      {error ? (
        <span className="field__error" id={`${id}-error`}>
          {error}
        </span>
      ) : (
        hint && (
          <span className="field__hint" id={`${id}-hint`}>
            {hint}
          </span>
        )
      )}
    </div>
  )
}
