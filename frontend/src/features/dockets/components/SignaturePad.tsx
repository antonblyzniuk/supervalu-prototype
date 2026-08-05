import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/Button'

interface SignaturePadProps {
  label: string
  /** Existing signature — a stored URL when editing, a data URL when re-signed. */
  value?: string | null
  onChange: (dataUrl: string | null) => void
  name?: string
  onNameChange?: (name: string) => void
}

/**
 * Finger/stylus/mouse signature capture.
 *
 * Uses Pointer Events so one code path covers touch, pen and mouse across
 * Safari, Chrome and Firefox, and redraws at devicePixelRatio so signatures
 * stay crisp on phones and retina screens.
 */
export function SignaturePad({ label, value, onChange, name, onNameChange }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const lastPoint = useRef<{ x: number; y: number } | null>(null)
  const [hasInk, setHasInk] = useState(false)

  const isStoredImage = Boolean(value) && !value?.startsWith('data:')

  const prepareCanvas = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const ratio = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    if (canvas.width !== Math.round(rect.width * ratio)) {
      canvas.width = Math.round(rect.width * ratio)
      canvas.height = Math.round(rect.height * ratio)
    }
    const context = canvas.getContext('2d')
    if (!context) return null
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    context.lineWidth = 2.4
    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.strokeStyle = '#1a1f18'
    return context
  }, [])

  // Keep the drawing surface matched to its rendered size on rotate/resize.
  useEffect(() => {
    const onResize = () => {
      const canvas = canvasRef.current
      if (!canvas || hasInk) return
      prepareCanvas()
    }
    window.addEventListener('resize', onResize)
    onResize()
    return () => window.removeEventListener('resize', onResize)
  }, [prepareCanvas, hasInk])

  const pointFrom = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    prepareCanvas()
    drawing.current = true
    lastPoint.current = pointFrom(event)
    setHasInk(true)
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return
    const context = canvasRef.current?.getContext('2d')
    const previous = lastPoint.current
    if (!context || !previous) return
    const point = pointFrom(event)
    context.beginPath()
    context.moveTo(previous.x, previous.y)
    context.lineTo(point.x, point.y)
    context.stroke()
    lastPoint.current = point
  }

  const commit = () => {
    if (!drawing.current) return
    drawing.current = false
    lastPoint.current = null
    const canvas = canvasRef.current
    if (canvas) onChange(canvas.toDataURL('image/png'))
  }

  const clear = () => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height)
    setHasInk(false)
    onChange(null)
  }

  return (
    <div className="u-stack-sm">
      <div className="u-spread">
        <span className="field__label">{label}</span>
        {(hasInk || value) && (
          <Button variant="ghost" size="sm" onClick={clear}>
            Clear
          </Button>
        )}
      </div>

      {onNameChange && (
        <input
          className="input"
          placeholder="Full name"
          value={name ?? ''}
          onChange={(event) => onNameChange(event.target.value)}
          aria-label={`${label} name`}
        />
      )}

      {isStoredImage && !hasInk ? (
        <div className="sig-preview">
          <div className="sig-preview__item">
            <img src={value as string} alt={`${label} signature`} />
            <div className="u-subtle" style={{ fontSize: 'var(--text-2xs)' }}>
              Signed · draw below to replace
            </div>
          </div>
        </div>
      ) : null}

      <div className="sigpad">
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={commit}
          onPointerLeave={commit}
          onPointerCancel={commit}
          aria-label={`${label} signature pad`}
          role="img"
        />
        <div className="sigpad__baseline" />
        {!hasInk && <div className="sigpad__placeholder">Sign here with your finger</div>}
      </div>
    </div>
  )
}
