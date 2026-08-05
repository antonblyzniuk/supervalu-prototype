import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'on-brand'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  block?: boolean
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  loading = false,
  icon,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  const classes = [
    'btn',
    variant !== 'primary' && `btn--${variant}`,
    size !== 'md' && `btn--${size}`,
    block && 'btn--block',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type={type} className={classes} disabled={disabled || loading} {...rest}>
      {loading ? (
        <span
          className={`spinner ${variant === 'primary' ? 'spinner--inverse' : ''}`}
          aria-hidden="true"
        />
      ) : (
        icon
      )}
      {children}
    </button>
  )
}
