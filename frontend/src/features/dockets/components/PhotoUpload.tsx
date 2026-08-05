import { useId, useState, type ChangeEvent } from 'react'

import type { DocketPhoto } from '../types'

const MAX_DIMENSION = 1600
const JPEG_QUALITY = 0.82

interface PhotoUploadProps {
  photos: DocketPhoto[]
  onChange: (photos: DocketPhoto[]) => void
}

/**
 * Reads camera/gallery files and downscales them in a canvas before they reach
 * the API — a modern phone photo is 4-8 MB, which would blow the upload limit
 * and make the docket list crawl.
 */
async function toCompressedDataUrl(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)

  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas is unavailable')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()

  return canvas.toDataURL('image/jpeg', JPEG_QUALITY)
}

export function PhotoUpload({ photos, onChange }: PhotoUploadProps) {
  const inputId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = '' // Allow picking the same file twice.
    if (!files.length) return

    setBusy(true)
    setError(null)
    try {
      const capturedAt = new Date().toISOString()
      const added = await Promise.all(
        files.map(async (file) => ({
          image: await toCompressedDataUrl(file),
          caption: file.name.slice(0, 160),
          captured_at: capturedAt,
        })),
      )
      onChange([...photos, ...added])
    } catch {
      setError('Could not read one of those images. Try again or pick a different photo.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="u-stack-sm">
      <label className="photo-drop" htmlFor={inputId}>
        <input
          id={inputId}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFiles}
          disabled={busy}
        />
        <div style={{ fontSize: '1.5rem' }} aria-hidden="true">
          📷
        </div>
        <div>{busy ? 'Processing photos…' : 'Tap to attach docket photos'}</div>
        <div className="u-subtle" style={{ fontSize: 'var(--text-xs)' }}>
          Camera or gallery · resized automatically
        </div>
      </label>

      {error && <div className="alert alert--error">{error}</div>}

      {photos.length > 0 && (
        <div className="photo-grid">
          {photos.map((photo, index) => (
            <figure className="photo-tile" key={photo.id ?? `${index}-${photo.caption}`}>
              <img src={photo.image} alt={photo.caption || `Docket photo ${index + 1}`} />
              <button
                type="button"
                className="photo-tile__remove"
                onClick={() => onChange(photos.filter((_, i) => i !== index))}
              >
                <span aria-hidden="true">✕</span>
                <span className="u-sr-only">Remove photo {index + 1}</span>
              </button>
              {photo.captured_at && (
                <figcaption className="photo-tile__stamp">
                  {new Date(photo.captured_at).toLocaleDateString('en-IE')}
                </figcaption>
              )}
            </figure>
          ))}
        </div>
      )}
    </div>
  )
}
