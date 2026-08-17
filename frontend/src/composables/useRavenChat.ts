// VERTO_RAVEN_NATIVE_CHAT_COMPOSABLE_TS_FIX_2026_06_10
import { computed, nextTick, ref, type Ref } from 'vue'
import {
  getChannelId,
  getChannelKeys,
  getMessages,
  getMobileChatBootstrap,
  getNewerMessages,
  getOrCreatePeriChannel,
  normaliseRavenMessage,
  sendTextMessage,
  sortMessagesOldestFirst,
  uploadFileWithMessage,
  type RavenChannel,
  type RavenMessage,
} from '../lib/ravenClient'

export function useRavenChat(options: {
  requestedChannel: Ref<string>
  isAiMode: Ref<boolean>
  defaultWorkspace: Ref<string>
}) {
  const loading = ref(true)
  const refreshing = ref(false)
  const sending = ref(false)
  const uploading = ref(false)
  const error = ref('')
  const composerError = ref('')

  const currentUser = ref('')
  const currentUserFullName = ref('')
  const channels = ref<RavenChannel[]>([])
  const activeChannel = ref<RavenChannel | null>(null)
  const messages = ref<RavenMessage[]>([])
  const hasOldMessages = ref(false)
  const hasNewMessages = ref(false)

  const activeChannelId = computed(() => getChannelId(activeChannel.value))
  const orderedMessages = computed(() => sortMessagesOldestFirst(messages.value))

  function findChannelByRequestedValue(requestedChannel: string) {
    const requested = requestedChannel.toLowerCase()

    return channels.value.find((channel) => {
      return getChannelKeys(channel).includes(requested)
    })
  }

  function setActiveChannelFromId(channelId: string) {
    const found = findChannelByRequestedValue(channelId)

    if (found) {
      activeChannel.value = found
      return
    }

    activeChannel.value = {
      name: channelId,
      channel_id: channelId,
      channel_name: channelId,
      workspace: options.defaultWorkspace.value,
    }
  }

  async function resolveInitialChannel() {
    const requested = options.requestedChannel.value

    if (requested) {
      setActiveChannelFromId(requested)
      return
    }

    if (options.isAiMode.value) {
      const periChannel = await getOrCreatePeriChannel()
      if (periChannel) {
        setActiveChannelFromId(periChannel)
        return
      }
    }

    activeChannel.value = channels.value[0] || null
  }

  async function load() {
    loading.value = true
    error.value = ''
    composerError.value = ''

    try {
      const boot = await getMobileChatBootstrap()

      currentUser.value = boot.current_user || ''
      currentUserFullName.value = boot.current_user_full_name || ''
      channels.value = boot.channels || []

      await resolveInitialChannel()
      await loadMessages()
    } catch (err) {
      if (err instanceof Error && err.message === 'Login required') return
      error.value = err instanceof Error ? err.message : 'Could not load Raven chat.'
    } finally {
      loading.value = false
    }
  }

  async function loadMessages() {
    if (!activeChannelId.value) {
      messages.value = []
      return
    }

    refreshing.value = true

    try {
      const data = await getMessages(activeChannelId.value, 50)
      messages.value = data.messages
      hasOldMessages.value = Boolean(data.has_old_messages)
      hasNewMessages.value = Boolean(data.has_new_messages)
    } catch (err) {
      if (err instanceof Error && err.message === 'Login required') return
      composerError.value = err instanceof Error ? err.message : 'Could not refresh Raven messages.'
    } finally {
      refreshing.value = false
    }
  }

  async function fetchNewer() {
    if (!activeChannelId.value) return

    const newest = sortMessagesOldestFirst(messages.value).at(-1)

    if (!newest?.name) {
      await loadMessages()
      return
    }

    try {
      const data = await getNewerMessages(activeChannelId.value, newest.name, 20)
      mergeMessages(data.messages)
      hasNewMessages.value = Boolean(data.has_new_messages)
    } catch {
      await loadMessages()
    }
  }

  function mergeMessages(incoming: RavenMessage[]) {
    if (!incoming.length) return

    const byName = new Map<string, RavenMessage>()

    for (const message of messages.value) {
      byName.set(message.name, message)
    }

    for (const raw of incoming) {
      const message = normaliseRavenMessage(raw)
      const existing = byName.get(message.name)
      byName.set(message.name, existing ? { ...existing, ...message } : message)
    }

    messages.value = sortMessagesOldestFirst([...byName.values()])
  }

  function patchMessage(messageId: string, patch: Partial<RavenMessage>) {
    if (!messageId) return

    messages.value = messages.value.map((message) => {
      if (message.name !== messageId) return message
      return normaliseRavenMessage({ ...message, ...patch })
    })
  }

  function deleteMessage(messageId: string) {
    if (!messageId) return
    messages.value = messages.value.filter((message) => message.name !== messageId)
  }

  async function sendText(text: string, args: { isReply?: boolean; linkedMessage?: string | null } = {}) {
    const value = text.trim()

    if (!value || !activeChannelId.value || sending.value || uploading.value) {
      return null
    }

    sending.value = true
    composerError.value = ''

    try {
      const message = await sendTextMessage({
        channelId: activeChannelId.value,
        text: value,
        isReply: args.isReply,
        linkedMessage: args.linkedMessage,
      })

      mergeMessages([message])
      await nextTick()
      return message
    } catch (err) {
      if (err instanceof Error && err.message === 'Login required') return null
      composerError.value = err instanceof Error ? err.message : 'Could not send Raven message.'
      return null
    } finally {
      sending.value = false
    }
  }

  async function uploadFile(file: File, caption = '') {
    if (!activeChannelId.value || uploading.value) return null

    uploading.value = true
    composerError.value = ''

    try {
      const message = await uploadFileWithMessage({
        channelId: activeChannelId.value,
        file,
        caption,
        compressImages: true,
      })

      mergeMessages([message])
      return message
    } catch (err) {
      if (err instanceof Error && err.message === 'Login required') return null
      composerError.value = err instanceof Error ? err.message : 'Could not upload file to Raven.'
      return null
    } finally {
      uploading.value = false
    }
  }

  return {
    loading,
    refreshing,
    sending,
    uploading,
    error,
    composerError,
    currentUser,
    currentUserFullName,
    channels,
    activeChannel,
    activeChannelId,
    orderedMessages,
    messages,
    hasOldMessages,
    hasNewMessages,
    load,
    loadMessages,
    fetchNewer,
    mergeMessages,
    patchMessage,
    deleteMessage,
    sendText,
    uploadFile,
    setActiveChannelFromId,
  }
}
