// VERTO_RAVEN_NATIVE_CLIENT_TEXT_FIELD_PRIORITY_FIX_2026_06_10
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
}

export type MessagesPayload = {
  messages: RavenMessage[]
  has_old_messages?: boolean
  has_new_messages?: boolean
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
  if (!value.includes('.')) return ''
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

function pickRavenTextField(message: RavenMessage) {
  // Raven's source-of-truth display field is `text`.
  // Use nullish checks instead of `||` so we do not accidentally replace a valid
  // empty string with `content`, which is Raven's plain-text/search summary field.
  if (message.text !== undefined && message.text !== null) {
    return String(message.text)
  }

  if (message.message !== undefined && message.message !== null) {
    return String(message.message)
  }

  if (message.content !== undefined && message.content !== null) {
    return String(message.content)
  }

  return ''
}

export function normaliseRavenMessage(message: RavenMessage): RavenMessage {
  const text = pickRavenTextField(message)

  const normalised: RavenMessage = {
    ...message,
    owner: message.owner || message.sender || '',
    sender: message.sender || message.owner || '',
    message: message.message ?? text,
    content: message.content ?? message.message ?? text,
    text,
    channel_id: message.channel_id || message.channel || '',
    channel: message.channel || message.channel_id || '',
    is_bot_message: message.is_bot_message || Boolean(message.bot),
    bot: message.bot || null,
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

  return data.message
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
  const payload = new FormData()
  payload.append('channel_id', channelId)
  payload.append('limit', String(limit))

  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    '/api/method/raven.api.chat_stream.get_messages',
    {
      method: 'POST',
      body: payload,
    }
  )

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(normaliseRavenMessages(data.message.messages || [])),
  }
}

export async function getOlderMessages(channelId: string, fromMessage: string, limit = 20) {
  const payload = new FormData()
  payload.append('channel_id', channelId)
  payload.append('from_message', fromMessage)
  payload.append('limit', String(limit))

  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    '/api/method/raven.api.chat_stream.get_older_messages',
    {
      method: 'POST',
      body: payload,
    }
  )

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(normaliseRavenMessages(data.message.messages || [])),
  }
}

export async function getNewerMessages(channelId: string, fromMessage: string, limit = 20) {
  const payload = new FormData()
  payload.append('channel_id', channelId)
  payload.append('from_message', fromMessage)
  payload.append('limit', String(limit))

  const data = await apiRequest<FrappeResponse<MessagesPayload>>(
    '/api/method/raven.api.chat_stream.get_newer_messages',
    {
      method: 'POST',
      body: payload,
    }
  )

  return {
    ...data.message,
    messages: sortMessagesOldestFirst(normaliseRavenMessages(data.message.messages || [])),
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

  return {
    ...data.message,
    parent: data.message.parent ? normaliseRavenMessage(data.message.parent) : data.message.parent,
    replies: normaliseRavenMessages(data.message.replies || []),
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

  return {
    ...data.message,
    parent: data.message.parent ? normaliseRavenMessage(data.message.parent) : data.message.parent,
    replies: normaliseRavenMessages(data.message.replies || []),
  }
}
