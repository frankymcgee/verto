// WebKit can reject native Blob/File objects during IndexedDB persistence.
// Store their bytes before opening a transaction, then recreate a Blob for use.
export type AttachmentData = { type?: string; blob?: Blob; data?: ArrayBuffer }

export function hydrateAttachment<T extends AttachmentData>(attachment: T): T {
  if (attachment.blob || !attachment.data) return attachment
  return { ...attachment, blob: new Blob([attachment.data], { type: attachment.type || 'application/octet-stream' }) }
}

export async function serialiseAttachment<T extends AttachmentData>(attachment: T): Promise<T> {
  const data = attachment.data || await attachment.blob?.arrayBuffer()
  if (!data) throw new Error('The saved attachment data is unavailable. Keep the original photo and select it again.')
  return { ...attachment, data, blob: undefined }
}

export async function serialiseQueueAttachments<T extends { attachments?: AttachmentData[]; attachment?: AttachmentData }>(item: T): Promise<T> {
  return {
    ...item,
    ...(item.attachments ? { attachments: await Promise.all(item.attachments.map(serialiseAttachment)) } : {}),
    ...(item.attachment ? { attachment: await serialiseAttachment(item.attachment) } : {}),
  }
}

export function hydrateQueueAttachments<T extends { attachments?: AttachmentData[]; attachment?: AttachmentData }>(item: T): T {
  return {
    ...item,
    ...(item.attachments ? { attachments: item.attachments.map(hydrateAttachment) } : {}),
    ...(item.attachment ? { attachment: hydrateAttachment(item.attachment) } : {}),
  }
}
