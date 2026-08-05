import { createContext } from 'react'

export type ToastTone = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  tone: ToastTone
  message: string
}

export interface ToastContextValue {
  push: (message: string, tone?: ToastTone) => void
}

// Separate module so ToastProvider.tsx exports only components (Fast Refresh).
export const ToastContext = createContext<ToastContextValue | null>(null)
