import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  open: boolean
  title: ReactNode
  onClose: () => void
  footer?: ReactNode
  children: ReactNode
}

export function Modal({ open, title, onClose, footer, children }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  // Escape closes, and the body stops scrolling behind the sheet on mobile.
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeyDown)
    panelRef.current?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        tabIndex={-1}
        ref={panelRef}
      >
        <header className="modal__header">
          <h2>{title}</h2>
          <button type="button" className="btn btn--ghost btn--icon" onClick={onClose}>
            <span aria-hidden="true">✕</span>
            <span className="u-sr-only">Close</span>
          </button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}
