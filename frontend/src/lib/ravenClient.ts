// VERTO_RAVEN_CLIENT_NATIVE_MESSAGES_WITH_DOCUMENT_PREVIEWS_2026_07_01
import { apiRequest } from './api'

export type FrappeResponse<T> = {
  message: T
}

export type RavenChannel = {
  name: string
  channel_name?: string
  channel_id?: string
  workspace?: string
  type?: string
  description?: string
  is_direct_message?: boolean
  is_thread?: boolean
  is_ai_thread?: boolean
  [key: string]: any
}

export type RavenAttachment = {
  name?: string
  file_name?: string
  file_url: string
  file_thumbnail?: string
  is_private?: boolean
  file_size?: number
  extension?: string
  is_image?: boolean
  is_pdf?: boolean
  is_document?: boolean
}

export type RavenDocumentLink = {
  doctype: string
  docname: string
}

export type RavenPreviewField = {
  label: string
  value: string | number | null
}

export type RavenDocumentPreview = {
  doctype: string
  docname: string
  title?: string
  subtitle?: string
  route?: string
  preview_image?: string | null
  id?: string
  fields?: RavenPreviewField[]
  raw?: Record<string, any>
}

export type RavenMessage = {
  name: string
  owner: string
  sender?: string
  sender_full_name?: string
  user_image?: string
  creation: string
  modified?: string
  text?: string
  message?: string
  content?: string
  json?: any
  html?: string
  html_message?: string
  message_html?: string
  content_html?: string
  text_html?: string
  formatted_text?: string
  formatted_message?: string
  rich_text?: string
  rich_text_content?: string
  plain_text?: string
  channel_id?: string
  channel?: string
  bot?: string | null
  bot_image?: string | null
  is_bot_message?: 0 | 1 | boolean
  attachments?: RavenAttachment[]
  thread_count?: number
  number_of_replies?: number
  reply_count?: number
  replies_count?: number
  thread_replies_count?: number
  total_replies?: number
  reply_count_on_thread?: number
  thread_reply_count?: number
  is_thread?: 0 | 1 | boolean
  is_reply?: 0 | 1 | boolean
  linked_message?: string | null
  message_type?: 'Text' | 'Image' | 'File' | 'Poll' | 'System' | string
  file?: string
  file_thumbnail?: string
  file_size?: number
  thumbnail_width?: number
  thumbnail_height?: number
  image_width?: number
  image_height?: number
  link_doctype?: string
  link_document?: string
  document_links?: RavenDocumentLink[]
  document_preview?: RavenDocumentPreview | null
  linked_doctype?: string
  linked_docname?: string
  reference_doctype?: string
  reference_docname?: string
  document_type?: string
  document_name?: string
  message_reactions?: any
  _liked_by?: string
  hide_link_preview?: 0 | 1 | boolean
  blurhash?: string
  [key: string]: any
}

export type ChatBootstrap = {
  current_user: string
  current_user_full_name?: string
  channels: RavenChannel[]
  active_channel?: RavenChannel | null
  messages?: RavenMessage[]
  settings?: Record<string, any>
}

export type MessagesPayload = {
  messages: RavenMessage[]
  has_old_messages?: boolean
  has_new_messages?: boolean
  [key: string]: any
}

export type ThreadPayload = {
  parent: RavenMessage
  replies: RavenMessage[]
  thread_supported?: boolean
  thread_id?: string
  thread_pending?: boolean
}

export type PeriChannelPayload = {
  channel?: string | RavenChannel
  name?: string
  channel_id?: string
  channel_name?: string
  url?: string
  peri_bot_name?: string
  peri_bot_user?: string
  [key: string]: any
}

export function sortMessagesOldestFirst(items: RavenMessage[]) {
  return [...(items || [])].sort((a, b) => {
    const aTime = new Date(a.creation || '').getTime()
    const bTime = new Date(b.creation || '').getTime()

    if (Number.isFinite(aTime) && Number.isFinite(bTime) && aTime !== bTime) {
      return aTime - bTime
    }

    return String(a.name || '').localeCompare(String(b.name || ''))
  })
}

function getExtension(fileNameOrUrl?: string) {
  const value = String(fileNameOrUrl || '')

  if (!value.includes('.')) {
    return ''
  }

  return value.split('?')[0].split('#')[0].split('.').pop()?.toLowerCase() || ''
}

function buildAttachmentFromRavenFile(message: RavenMessage): RavenAttachment[] {
  const fileUrl = String(message.file || '').trim()

  if (!fileUrl) {
    return []
  }

  const fileName = fileUrl.includes('/')
    ? fileUrl.split('/').pop() || fileUrl
    : fileUrl

  const extension = getExtension(fileName)
  const messageType = String(message.message_type || '').toLowerCase()
  const isImage =
    messageType === 'image' ||
    ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(extension)

  return [
    {
      name: message.name,
      file_name: fileName,
      file_url: fileUrl,
      file_thumbnail: message.file_thumbnail || '',
      is_private: fileUrl.startsWith('/private/'),
      file_size: message.file_size || 0,
      extension,
      is_image: isImage,
      is_pdf: extension === 'pdf',
      is_document: ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'txt', 'pdf'].includes(extension),
    },
  ]
}

function isObjectLike(value: unknown) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function stringifyIfNeeded(value: unknown) {
  if (value === undefined || value === null) {
    return ''
  }

  if (typeof value === 'string') {
    return value
  }

  if (isObjectLike(value) || Array.isArray(value)) {
    try {
      return JSON.stringify(value)
    } catch {
      return ''
    }
  }

  return String(value)
}

function normaliseJsonBody(value: unknown) {
  if (value === undefined || value === null || value === '') {
    return ''
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()

    if (!trimmed) {
      return ''
    }

    try {
      const parsed = JSON.parse(trimmed)

      if (isObjectLike(parsed) && String((parsed as Record<string, any>).type || '') === 'doc') {
        return JSON.stringify(parsed)
      }

      return trimmed
    } catch {
      return trimmed
    }
  }

  if (isObjectLike(value) && String((value as Record<string, any>).type || '') === 'doc') {
    return stringifyIfNeeded(value)
  }

  return stringifyIfNeeded(value)
}

function hasLikelyRichFormatting(value: string) {
  const trimmed = String(value || '').trim()

  if (!trimmed) {
    return false
  }

  return (
    /<([a-z][\w:-]*)(?:\s[^>]*)?>[\s\S]*?<\/\1>/i.test(trimmed) ||
    /<(br|hr|img|input|meta|link)(?:\s[^>]*)?\/?>/i.test(trimmed) ||
    /&lt;[a-z][\s\S]*?&gt;/i.test(trimmed) ||
    (trimmed.startsWith('{') && trimmed.includes('"type"') && trimmed.includes('"doc"'))
  )
}

function getRichBodyCandidates(message: RavenMessage) {
  const raw = message as any

  return [
    normaliseJsonBody(raw.json),
    stringifyIfNeeded(raw.html),
    stringifyIfNeeded(raw.html_message),
    stringifyIfNeeded(raw.message_html),
    stringifyIfNeeded(raw.content_html),
    stringifyIfNeeded(raw.text_html),
    stringifyIfNeeded(raw.formatted_text),
    stringifyIfNeeded(raw.formatted_message),
    stringifyIfNeeded(raw.rich_text),
    stringifyIfNeeded(raw.rich_text_content),
    stringifyIfNeeded(raw.text),
    stringifyIfNeeded(raw.message),
    stringifyIfNeeded(raw.content),
  ].filter((value) => String(value || '').trim())
}

function getBestMessageBody(message: RavenMessage) {
  const richCandidates = getRichBodyCandidates(message)
  const explicitRich = richCandidates.find((value) => hasLikelyRichFormatting(value))

  if (explicitRich) {
    return explicitRich
  }

  return (
    stringifyIfNeeded(message.text) ||
    stringifyIfNeeded(message.message) ||
    stringifyIfNeeded(message.content) ||
    richCandidates[0] ||
    ''
  )
}

function previewKey(doctype: string, docname: string) {
  return `${doctype}::${docname}`
}

function mapPreviewDataToDocumentPreview(doctype: string, docname: string, raw: Record<string, any> | null): RavenDocumentPreview | null {
  if (!raw) {
    return null
  }

  const hiddenKeys = new Set([
    'preview_image',
    'preview_title',
    'id',
    'raven_document_link',
  ])

  const fields = Object.keys(raw)
    .filter((key) => !hiddenKeys.has(key) && raw[key] !== undefined && raw[key] !== null && String(raw[key]).trim() !== '')
    .map((key) => ({
      label: key,
      value: raw[key],
    }))

  return {
    doctype,
    docname,
    title: raw.preview_title || raw.id || docname,
    subtitle: doctype,
    route: raw.raven_document_link,
    preview_image: raw.preview_image || null,
    id: raw.id || docname,
    fields,
    raw,
  }
}

async function fetchDocumentPreviewData(doctype: string, docname: string) {
  const params = new URLSearchParams({
    doctype,
    docname,
  })

  try {
    const data = await apiRequest<FrappeResponse<Record<string, any> | null>>(
      `/api/method/raven.api.document_link.get_preview_data?${params.toString()}`
    )

    return mapPreviewDataToDocumentPreview(doctype, docname, data.message || null)
  } catch {
    return null
  }
}

async function enrichDocumentPreviews(messages: RavenMessage[]) {
  const links = messages
    .flatMap((message) => normaliseDocumentLinks(message))
    .filter((link) => link.doctype && link.docname)

  const uniqueLinks = Array.from(
    new Map(
      links.map((link) => [
        previewKey(link.doctype, link.docname),
        link,
      ])
    ).values()
  )

  if (!uniqueLinks.length) {
    return messages
  }

  const previews = await Promise.all(
    uniqueLinks.map(async (link) => {
      const preview = await fetchDocumentPreviewData(link.doctype, link.docname)

      return {
        key: previewKey(link.doctype, link.docname),
        preview,
      }
    })
  )

  const previewMap = new Map(
    previews
      .filter((item) => item.preview)
      .map((item) => [item.key, item.preview as RavenDocumentPreview])
  )

  return messages.map((message) => {
    if (message.document_preview) {
      return message
    }

    const primaryLink = normaliseDocumentLinks(message)[0]

    if (!primaryLink) {
      return message
    }

    const preview = previewMap.get(previewKey(primaryLink.doctype, primaryLink.docname))

    if (!preview) {
      return message
    }

    return {
      ...message,
      document_preview: preview,
    }
  })
}

async function normaliseAndEnrichRavenMessages(items: RavenMessage[]) {
  const normalised = normaliseRavenMessages(items)
  return enrichDocumentPreviews(normalised)
}

function normaliseDocumentLinks(message: RavenMessage): RavenDocumentLink[] {
  const existingLinks = Array.isArray(message.document_links)
    ? message.document_links
        .map((link) => ({
          doctype: String(link.doctype || '').trim(),
          docname: String(link.docname || '').trim(),
        }))
        .filter((link) => link.doctype && link.docname)
    : []

  const preview = message.document_preview

  const doctype = String(
    message.link_doctype ||
      message.linked_doctype ||
      message.reference_doctype ||
      message.document_type ||
      preview?.doctype ||
      ''
  ).trim()

  const docname = String(
    message.link_document ||
      message.linked_docname ||
      message.reference_docname ||
      message.document_name ||
      preview?.docname ||
      ''
  ).trim()

  if (doctype && docname && !existingLinks.some((link) => link.doctype === doctype && link.docname === docname)) {
    existingLinks.unshift({
      doctype,
      docname,
    })
  }

  return existingLinks
}

export function normaliseRavenMessage(message: RavenMessage): RavenMessage {
  const displayBody = getBestMessageBody(message)
  const plainFallback = message.text || message.message || message.content || ''
  const documentLinks = normaliseDocumentLinks(message)
  const primaryDocumentLink = documentLinks[0]

  const linkDoctype = String(
    message.link_doctype ||
      message.linked_doctype ||
      message.reference_doctype ||
      message.document_type ||
      primaryDocumentLink?.doctype ||
      message.document_preview?.doctype ||
      ''
  ).trim()

  const linkDocument = String(
    message.link_document ||
      message.linked_docname ||
      message.reference_docname ||
      message.document_name ||
      primaryDocumentLink?.docname ||
      message.document_preview?.docname ||
      ''
  ).trim()

  const normalised: RavenMessage = {
    ...message,
    owner: message.owner || message.sender || '',
    sender: message.sender || message.owner || '',
    text: displayBody || plainFallback || '',
    message: displayBody || plainFallback || '',
    content: displayBody || plainFallback || '',
    plain_text: plainFallback || '',
    json: (message as any).json ?? null,
    channel_id: message.channel_id || message.channel || '',
    channel: message.channel || message.channel_id || '',
    is_bot_message: message.is_bot_message || Boolean(message.bot),
    bot: message.bot || null,
    link_doctype: linkDoctype || undefined,
    link_document: linkDocument || undefined,
    linked_doctype: message.linked_doctype || linkDoctype || undefined,
    linked_docname: message.linked_docname || linkDocument || undefined,
    reference_doctype: message.reference_doctype || linkDoctype || undefined,
    reference_docname: message.reference_docname || linkDocument || undefined,
    document_type: message.document_type || linkDoctype || undefined,
    document_name: message.document_name || linkDocument || undefined,
    document_links: documentLinks,
    document_preview: message.document_preview || null,
  }

  if (!normalised.attachments?.length) {
    normalised.attachments = buildAttachmentFromRavenFile(normalised)
  }

  return normalised
}

export function normaliseRavenMessages(items: RavenMessage[]) {
  return (items || []).map((message) => normaliseRavenMessage(message))
}

export function getChannelId(channel?: RavenChannel | string | null) {
  if (!channel) return ''
  if (typeof channel === 'string') return channel
  return channel.name || channel.channel_id || channel.channel_name || ''
}

export function getChannelLabel(channel?: RavenChannel | null) {
  if (!channel) return 'Chat'
  return channel.channel_name || channel.name || channel.channel_id || 'Chat'
}

export function getChannelKeys(channel: RavenChannel) {
  return [channel.name, channel.channel_name, channel.channel_id]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase())
}

function appendOptional(form: FormData, key: string, value: unknown) {
  if (value === undefined || value === null) return
  form.append(key, String(value))
}

export async function getMobileChatBootstrap() {
  const data = await apiRequest<FrappeResponse<ChatBootstrap>>(
    '/api/method/verto.api.mobile.raven.get_mobile_chat_bootstrap'
  )

  return {
    ...data.message,
    messages: normaliseRavenMessages(data.message.messages || []),
  }
}

export async function getOrCreatePeriChannel() {
  const data = await apiRequest<FrappeResponse<PeriChannelPayload>>(
    '/api/method/verto.api.mobile.raven.get_or_create_peri_channel'
  )

  const payload = data.message
  const channel = payload.channel || payload

  if (typeof channel === 'string') {
    return channel
  }

  return channel?.name || channel?.channel_id || payload.name || payload.channel_id || ''
}

export async function getMessages(channelId: string, limit = 50) {
  const params = new URLSearchParams({
    channel_id: channelId,
  })

  // Keep using Raven's native chat stream for message bodies. The Verto wrapper
  // enriches document previews, but it can flatten rich message bodies back to
  // plain text. Document previews are enriched separately below.
  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    `/api/method/raven.api.chat_stream.get_messages?${params.toString()}`
  )

  const messages = await normaliseAndEnrichRavenMessages(data.message.messages || [])

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(messages).slice(-limit),
  }
}

export async function getOlderMessages(channelId: string, fromMessage: string, limit = 20) {
  const payload = new FormData()
  payload.append('channel_id', channelId)
  payload.append('from_message', fromMessage)

  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    '/api/method/raven.api.chat_stream.get_older_messages',
    {
      method: 'POST',
      body: payload,
    }
  )

  const messages = await normaliseAndEnrichRavenMessages(data.message.messages || [])

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(messages).slice(-limit),
  }
}

export async function getNewerMessages(channelId: string, fromMessage: string, limit = 20) {
  const payload = new FormData()
  payload.append('channel_id', channelId)
  payload.append('from_message', fromMessage)

  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    '/api/method/raven.api.chat_stream.get_newer_messages',
    {
      method: 'POST',
      body: payload,
    }
  )

  const messages = await normaliseAndEnrichRavenMessages(data.message.messages || [])

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(messages).slice(-limit),
  }
}

export async function sendTextMessage(args: {
  channelId: string
  text: string
  isReply?: boolean
  linkedMessage?: string | null
  sendSilently?: boolean
}) {
  const payload = new FormData()
  payload.append('channel_id', args.channelId)
  payload.append('text', args.text)
  payload.append('is_reply', args.isReply ? '1' : '0')
  appendOptional(payload, 'linked_message', args.linkedMessage || '')
  payload.append('send_silently', args.sendSilently ? '1' : '0')

  const data = await apiRequest<FrappeResponse<RavenMessage>>(
    '/api/method/raven.api.raven_message.send_message',
    {
      method: 'POST',
      body: payload,
    }
  )

  return normaliseRavenMessage(data.message)
}

export async function uploadFileWithMessage(args: {
  channelId: string
  file: File
  caption?: string
  compressImages?: boolean
  isReply?: boolean
  linkedMessage?: string | null
}) {
  const payload = new FormData()
  payload.append('file', args.file)
  payload.append('channelID', args.channelId)
  payload.append('caption', args.caption || '')
  payload.append('compressImages', args.compressImages ? '1' : '0')
  payload.append('is_reply', args.isReply ? '1' : '0')
  payload.append('linked_message', args.linkedMessage || '')
  payload.append('doctype', 'Raven Message')
  payload.append('fieldname', 'file')
  payload.append('is_private', '1')

  const data = await apiRequest<FrappeResponse<RavenMessage>>(
    '/api/method/raven.api.upload_file.upload_file_with_message',
    {
      method: 'POST',
      body: payload,
    }
  )

  return normaliseRavenMessage(data.message)
}

export async function getExistingMessageThread(messageName: string) {
  const payload = new FormData()
  payload.append('message', messageName)

  const data = await apiRequest<FrappeResponse<ThreadPayload>>(
    '/api/method/verto.api.mobile.raven.get_existing_message_thread',
    {
      method: 'POST',
      body: payload,
    }
  )

  const replies = await normaliseAndEnrichRavenMessages(data.message.replies || [])
  const parent = data.message.parent
    ? (await normaliseAndEnrichRavenMessages([data.message.parent]))[0]
    : data.message.parent

  return {
    ...data.message,
    parent,
    replies,
  }
}

export async function getMessageThread(messageName: string) {
  const payload = new FormData()
  payload.append('message', messageName)

  const data = await apiRequest<FrappeResponse<ThreadPayload>>(
    '/api/method/verto.api.mobile.raven.get_message_thread',
    {
      method: 'POST',
      body: payload,
    }
  )

  const replies = await normaliseAndEnrichRavenMessages(data.message.replies || [])
  const parent = data.message.parent
    ? (await normaliseAndEnrichRavenMessages([data.message.parent]))[0]
    : data.message.parent

  return {
    ...data.message,
    parent,
    replies,
  }
}
