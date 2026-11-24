export type PhotoPoint = { x: number; y: number }
export type PhotoMark = {
  tool: 'arrow' | 'circle' | 'note'
  start: PhotoPoint
  end: PhotoPoint
  color: string
  text?: string
}

export function photoPoint(clientX: number, clientY: number, rect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>): PhotoPoint {
  return {
    x: Math.max(0, Math.min(1, (clientX - rect.left) / (rect.width || 1))),
    y: Math.max(0, Math.min(1, (clientY - rect.top) / (rect.height || 1))),
  }
}

export function drawPhotoMarks(ctx: CanvasRenderingContext2D, marks: PhotoMark[], width: number, height: number) {
  const scale = Math.max(1, Math.min(width, height) / 500)
  ctx.save()
  ctx.lineWidth = 3 * scale
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const mark of marks) {
    const x = mark.start.x * width, y = mark.start.y * height
    const endX = mark.end.x * width, endY = mark.end.y * height
    ctx.strokeStyle = mark.color
    ctx.fillStyle = mark.color
    ctx.beginPath()
    if (mark.tool === 'circle') {
      ctx.ellipse((x + endX) / 2, (y + endY) / 2, Math.max(1, Math.abs(endX - x) / 2), Math.max(1, Math.abs(endY - y) / 2), 0, 0, Math.PI * 2)
      ctx.stroke()
    } else if (mark.tool === 'arrow') {
      const angle = Math.atan2(endY - y, endX - x)
      const head = 14 * scale
      ctx.moveTo(x, y)
      ctx.lineTo(endX, endY)
      ctx.moveTo(endX - head * Math.cos(angle - Math.PI / 6), endY - head * Math.sin(angle - Math.PI / 6))
      ctx.lineTo(endX, endY)
      ctx.lineTo(endX - head * Math.cos(angle + Math.PI / 6), endY - head * Math.sin(angle + Math.PI / 6))
      ctx.stroke()
    } else {
      const fontSize = 16 * scale
      ctx.font = `600 ${fontSize}px sans-serif`
      const padding = 5 * scale
      // Shift edge-placed notes inward so their text remains inside the photo.
      const left = Math.max(0, Math.min(x, width - Math.min(width, 240 * scale)))
      const maxTextWidth = Math.max(1, width - left - padding * 2)
      const lines = String(mark.text || '').slice(0, 200).split('\n').flatMap(line => {
        const wrapped: string[] = []
        let current = ''
        for (const character of line) {
          if (current && ctx.measureText(current + character).width > maxTextWidth) {
            wrapped.push(current); current = ''
          }
          current += character
        }
        wrapped.push(current)
        return wrapped
      })
      const lineHeight = fontSize * 1.3
      const top = Math.min(y, Math.max(0, height - lines.length * lineHeight - padding * 2))
      const boxWidth = Math.min(width - left, Math.max(...lines.map(line => ctx.measureText(line).width), 0) + padding * 2)
      ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
      ctx.fillRect(left, top, boxWidth, lines.length * lineHeight + padding * 2)
      ctx.fillStyle = mark.color
      ctx.textBaseline = 'top'
      lines.forEach((line, index) => ctx.fillText(line, left + padding, top + padding + index * lineHeight, maxTextWidth))
    }
  }
  ctx.restore()
}

export async function exportAnnotatedPhoto(canvas: HTMLCanvasElement, original: File): Promise<File> {
  // Add the label outside the image so no evidence is covered by our own caption.
  const output = document.createElement('canvas')
  const footer = Math.max(36, Math.round(canvas.width / 40))
  output.width = canvas.width
  output.height = canvas.height + footer
  const ctx = output.getContext('2d')
  if (!ctx) throw new Error('Photo annotation is not supported by this browser.')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, output.width, output.height)
  ctx.drawImage(canvas, 0, 0)
  ctx.fillStyle = '#111'
  ctx.font = `${Math.max(12, footer * 0.4)}px sans-serif`
  ctx.textBaseline = 'middle'
  ctx.fillText(`ANNOTATED COPY · Original: ${original.name}`, 10, canvas.height + footer / 2, output.width - 20)
  const blob = await new Promise<Blob>((resolve, reject) => {
    output.toBlob(value => value ? resolve(value) : reject(new Error('Could not save the annotated photo.')), 'image/jpeg', 0.92)
  })
  const suffix = typeof crypto.randomUUID === 'function' ? crypto.randomUUID().slice(0, 8) : String(Date.now())
  return new File([blob], `${original.name.replace(/\.[^.]+$/, '')}-annotated-${suffix}.jpg`, { type: 'image/jpeg', lastModified: Date.now() })
}
