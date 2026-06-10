<!-- VERTO_CHAT_RAVEN_NATIVE_CLIENT_FORCED_POLLING_2026_06_10 -->
<template>
  <section class="min-h-screen bg-surface-gray-1">
    <main class="flex h-[calc(100vh-3.5rem-var(--mobile-bottom-tabs-height,4rem))] flex-col">
      <div
        v-if="chat.loading.value"
        class="space-y-3 p-3"
      >
        <Card class="p-3">
          <div class="space-y-3">
            <div class="h-4 w-40 rounded bg-surface-gray-3" />
            <div class="h-10 rounded-xl bg-surface-gray-2" />
            <div class="h-10 rounded-xl bg-surface-gray-2" />
            <div class="h-32 rounded-xl bg-surface-gray-2" />
          </div>
        </Card>
      </div>

      <div
        v-else-if="chat.error.value"
        class="p-3"
      >
        <Card class="border border-red-200 bg-red-50 p-3">
          <p class="text-sm font-medium text-red-800">
            Could not load chat
          </p>

          <p class="mt-1 text-sm text-red-700">
            {{ chat.error.value }}
          </p>

          <Button
            variant="solid"
            theme="gray"
            class="mt-3 w-full justify-center"
            @click="reloadChat"
          >
            Retry
          </Button>
        </Card>
      </div>

      <template v-else>
        <div class="border-b border-outline-gray-1 bg-surface-white px-3 py-2">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-ink-gray-9">
                {{ activeChannelLabel }}
              </p>

              <p
                v-if="isAiMode"
                class="truncate text-xs text-blue-600"
              >
                {{ periAssistantLabel }}
              </p>

              <p
                v-else-if="chat.activeChannel.value?.description"
                class="truncate text-xs text-ink-gray-5"
              >
                {{ chat.activeChannel.value.description }}
              </p>

              <p
                v-else
                class="truncate text-xs text-ink-gray-5"
              >
                {{ chat.orderedMessages.value.length }} {{ chat.orderedMessages.value.length === 1 ? 'message' : 'messages' }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-1 text-[11px] text-ink-gray-5">
              <span
                class="h-2 w-2 rounded-full"
                :class="realtime.ready.value ? 'bg-green-500' : 'bg-amber-500'"
              />
              <span>{{ realtime.status.value }}</span>
            </div>
          </div>
        </div>

        <div
          ref="messagesEl"
          class="flex-1 space-y-3 overflow-y-auto px-3 py-3"
        >
          <Card
            v-if="!chat.activeChannel.value"
            class="p-4"
          >
            <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center">
              <p class="text-sm font-medium text-ink-gray-7">
                No channel selected.
              </p>
            </div>
          </Card>

          <Card
            v-else-if="chat.orderedMessages.value.length === 0"
            class="p-4"
          >
            <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center">
              <p class="text-sm font-medium text-ink-gray-7">
                No messages yet.
              </p>

              <p class="mt-1 text-sm text-ink-gray-5">
                Send the first message in this channel.
              </p>
            </div>
          </Card>

          <div
            v-for="message in chat.orderedMessages.value"
            :key="message.name"
            class="flex gap-2"
            :class="isOwnMessage(message) ? 'justify-end' : 'justify-start'"
          >
            <Avatar
              v-if="!isOwnMessage(message)"
              :image="getMessageAvatarImage(message)"
              :label="getMessageInitials(message)"
              size="sm"
              class="mt-1 shrink-0"
            />

            <div
              class="max-w-[86%] rounded-2xl px-3 py-2 shadow-sm"
              :class="isOwnMessage(message)
                ? 'bg-blue-600 text-white'
                : 'border border-outline-gray-1 bg-surface-white text-ink-gray-9'"
            >
              <div
                class="mb-1 text-xs font-semibold"
                :class="isOwnMessage(message) ? 'text-white/80' : 'text-ink-gray-6'"
              >
                {{ getMessageDisplayName(message) }}
              </div>

              <div
                v-if="getVisibleMessageHtml(message)"
                class="rich-message-html break-words text-sm leading-relaxed"
                :class="isOwnMessage(message) ? 'text-white' : 'text-ink-gray-8'"
                v-html="getVisibleMessageHtml(message)"
              />

              <div
                v-if="message.attachments?.length"
                class="mt-2 space-y-2"
              >
                <template
                  v-for="attachment in message.attachments"
                  :key="attachment.name || attachment.file_url"
                >
                  <button
                    v-if="isImageAttachment(attachment)"
                    type="button"
                    class="block w-full overflow-hidden rounded-xl text-left"
                    @click="openPreview(attachment)"
                  >
                    <img
                      :src="attachment.file_thumbnail || attachment.file_url"
                      :alt="attachment.file_name || 'Image attachment'"
                      class="max-h-64 w-full object-cover"
                      loading="lazy"
                      @load="scrollToBottom"
                    >
                  </button>

                  <button
                    v-else
                    type="button"
                    class="flex w-full items-center gap-3 rounded-xl border p-3 text-left"
                    :class="isOwnMessage(message)
                      ? 'border-white/20 bg-white/15'
                      : 'border-outline-gray-1 bg-surface-gray-1'"
                    @click="openPreview(attachment)"
                  >
                    <div
                      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-semibold uppercase"
                      :class="isOwnMessage(message)
                        ? 'bg-white/20 text-white'
                        : 'bg-surface-white text-ink-gray-7'"
                    >
                      {{ getAttachmentLabel(attachment) }}
                    </div>

                    <div class="min-w-0 flex-1">
                      <p
                        class="truncate text-sm font-medium"
                        :class="isOwnMessage(message) ? 'text-white' : 'text-ink-gray-9'"
                      >
                        {{ attachment.file_name || 'Attachment' }}
                      </p>

                      <p
                        class="text-xs"
                        :class="isOwnMessage(message) ? 'text-white/75' : 'text-ink-gray-5'"
                      >
                        {{ formatFileSize(attachment.file_size || 0) }} · Tap to preview
                      </p>
                    </div>
                  </button>
                </template>
              </div>

              <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
                <div
                  class="text-[11px]"
                  :class="isOwnMessage(message) ? 'text-white/75' : 'text-ink-gray-5'"
                >
                  {{ formatMessageTime(message.creation) }}
                </div>

                <button
                  v-if="shouldShowThreadButton(message)"
                  type="button"
                  class="rounded-full px-2.5 py-1 text-[11px] font-semibold"
                  :class="isOwnMessage(message)
                    ? 'bg-white/15 text-white'
                    : 'bg-blue-50 text-blue-700'"
                  @click="openThread(message)"
                >
                  {{ getThreadButtonLabel(message) }}
                </button>
              </div>
            </div>

            <Avatar
              v-if="isOwnMessage(message)"
              :image="getMessageAvatarImage(message)"
              :label="getMessageInitials(message)"
              size="sm"
              class="mt-1 shrink-0"
            />
          </div>
        </div>

        <form
          class="border-t border-outline-gray-1 bg-surface-white p-3"
          @submit.prevent="sendDraft"
        >
          <div class="flex items-end gap-2">
            <input
              ref="fileInputEl"
              type="file"
              :accept="isAiMode ? 'image/*' : '*'"
              class="hidden"
              @change="handleFileSelected"
            >

            <Button
              type="button"
              variant="subtle"
              theme="gray"
              class="h-10 w-10 shrink-0 justify-center rounded-full text-lg font-semibold"
              :loading="chat.uploading.value"
              :disabled="chat.uploading.value || chat.sending.value || !chat.activeChannel.value"
              aria-label="Upload file"
              @click="openFilePicker"
            >
              +
            </Button>

            <Textarea
              v-model="draft"
              class="min-w-0 flex-1"
              :placeholder="isAiMode ? 'Message or add an image for PERI' : 'Message'"
              :rows="1"
              :disabled="chat.sending.value || chat.uploading.value || !chat.activeChannel.value"
              @keydown.enter.exact.prevent="sendDraft"
            />

            <Button
              type="submit"
              variant="solid"
              theme="gray"
              :loading="chat.sending.value"
              :disabled="chat.sending.value || chat.uploading.value || !chat.activeChannel.value || !draft.trim()"
            >
              Send
            </Button>
          </div>

          <p
            v-if="chat.uploading.value"
            class="mt-2 text-xs text-ink-gray-5"
          >
            Uploading file to Raven...
          </p>

          <p
            v-if="chat.composerError.value"
            class="mt-2 text-sm text-red-600"
          >
            {{ chat.composerError.value }}
          </p>
        </form>
      </template>
    </main>

    <!-- File Attachment Preview Drawer -->
    <div
      v-if="previewAttachment"
      class="fixed inset-0 z-[70] flex items-end bg-black/60"
      @click.self="closePreview"
    >
      <Card class="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
        <div class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-ink-gray-9">
              {{ previewAttachment.file_name || 'Attachment' }}
            </p>

            <p class="text-xs text-ink-gray-5">
              {{ formatFileSize(previewAttachment.file_size || 0) }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            @click="closePreview"
          >
            Close
          </Button>
        </div>

        <div class="flex-1 overflow-auto bg-surface-gray-1 p-3">
          <img
            v-if="isImageAttachment(previewAttachment)"
            :src="previewAttachment.file_url"
            :alt="previewAttachment.file_name || 'Image attachment'"
            class="mx-auto max-h-[76vh] rounded-xl object-contain"
          >

          <iframe
            v-else-if="canIframePreview(previewAttachment)"
            :src="previewAttachment.file_url"
            class="h-[76vh] w-full rounded-xl border border-outline-gray-1 bg-surface-white"
          />

          <Card
            v-else
            class="p-4"
          >
            <div class="flex items-start gap-3">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-surface-gray-2 text-xs font-semibold uppercase text-ink-gray-7">
                {{ getAttachmentLabel(previewAttachment) }}
              </div>

              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-semibold text-ink-gray-9">
                  {{ previewAttachment.file_name || 'Attachment' }}
                </p>

                <p class="mt-1 text-sm text-ink-gray-5">
                  This file type may not preview inline on all devices. Open it to view or download.
                </p>
              </div>
            </div>

            <Button
              as="a"
              :href="previewAttachment.file_url"
              target="_blank"
              rel="noopener noreferrer"
              variant="solid"
              theme="gray"
              class="mt-4 w-full justify-center"
            >
              Open File
            </Button>
          </Card>
        </div>
      </Card>
    </div>

    <!-- Thread Drawer -->
    <div
      v-if="threadOpen"
      class="fixed inset-0 z-[65] flex items-end bg-black/50"
      @click.self="closeThread"
    >
      <Card class="flex max-h-[88vh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
        <div class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
          <div class="min-w-0">
            <p class="truncate text-base font-semibold text-ink-gray-9">
              Thread
            </p>

            <p class="truncate text-xs text-ink-gray-5">
              {{ orderedThreadReplies.length }} {{ orderedThreadReplies.length === 1 ? 'reply' : 'replies' }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            @click="closeThread"
          >
            Close
          </Button>
        </div>

        <div
          ref="threadMessagesEl"
          class="flex-1 space-y-3 overflow-y-auto bg-surface-gray-1 p-3"
        >
          <Card
            v-if="threadLoading"
            class="p-3"
          >
            <div class="space-y-3">
              <div class="h-4 w-32 rounded bg-surface-gray-3" />
              <div class="h-20 rounded-xl bg-surface-gray-2" />
            </div>
          </Card>

          <template v-else>
            <Card
              v-if="threadParent"
              class="p-3"
            >
              <p class="text-xs font-semibold text-ink-gray-7">
                {{ getMessageDisplayName(threadParent) }}
              </p>

              <div
                v-if="getVisibleMessageHtml(threadParent)"
                class="rich-message-html mt-1 break-words text-sm text-ink-gray-8"
                v-html="getVisibleMessageHtml(threadParent)"
              />
            </Card>

            <div
              v-for="reply in orderedThreadReplies"
              :key="reply.name"
              class="flex gap-2"
              :class="isOwnMessage(reply) ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[82%] rounded-2xl px-3 py-2 shadow-sm"
                :class="isOwnMessage(reply)
                  ? 'bg-blue-600 text-white'
                  : 'border border-outline-gray-1 bg-surface-white text-ink-gray-9'"
              >
                <div
                  class="mb-1 text-xs font-semibold"
                  :class="isOwnMessage(reply) ? 'text-white/80' : 'text-ink-gray-6'"
                >
                  {{ getMessageDisplayName(reply) }}
                </div>

                <div
                  v-if="getVisibleMessageHtml(reply)"
                  class="rich-message-html break-words text-sm leading-relaxed"
                  :class="isOwnMessage(reply) ? 'text-white' : 'text-ink-gray-8'"
                  v-html="getVisibleMessageHtml(reply)"
                />

                <div
                  class="mt-1 text-[11px]"
                  :class="isOwnMessage(reply) ? 'text-white/75' : 'text-ink-gray-5'"
                >
                  {{ formatMessageTime(reply.creation) }}
                </div>
              </div>
            </div>

            <Card
              v-if="!orderedThreadReplies.length && !threadLoading"
              class="p-3"
            >
              <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-5 text-center">
                <p class="text-sm font-medium text-ink-gray-7">
                  No replies yet.
                </p>
              </div>
            </Card>

            <Card
              v-if="threadError"
              class="border border-yellow-200 bg-yellow-50 p-3"
            >
              <p class="text-sm text-yellow-800">
                {{ threadError }}
              </p>
            </Card>
          </template>
        </div>

        <form
          class="sticky bottom-0 z-10 border-t border-outline-gray-1 bg-surface-white p-3"
          @submit.prevent="sendThreadReply"
        >
          <div class="flex items-end gap-2">
            <Textarea
              v-model="threadDraft"
              class="min-w-0 flex-1"
              placeholder="Reply to thread"
              :rows="1"
              :disabled="threadSending || !activeThreadId"
              @keydown.enter.exact.prevent="sendThreadReply"
            />

            <Button
              type="submit"
              variant="solid"
              theme="gray"
              :loading="threadSending"
              :disabled="threadSending || !activeThreadId || !threadDraft.trim()"
            >
              Reply
            </Button>
          </div>
        </form>
      </Card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Avatar,
  Button,
  Card,
  Textarea,
} from 'frappe-ui'
import { useMobileBoot } from '../lib/mobileBoot'
import {
  getChannelLabel,
  getExistingMessageThread,
  getMessageThread,
  getMessages,
  normaliseRavenMessage,
  sendTextMessage,
  sortMessagesOldestFirst,
  type RavenAttachment,
  type RavenMessage,
} from '../lib/ravenClient'
import { useRavenChat } from '../composables/useRavenChat'
import { useRavenRealtime } from '../composables/useRavenRealtime'

const route = useRoute()
const router = useRouter()

const {
  loadMobileBoot,
  defaultWorkspace,
  periBotName,
  user,
  userFullname,
} = useMobileBoot()

const messagesEl = ref<HTMLElement | null>(null)
const threadMessagesEl = ref<HTMLElement | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const previewAttachment = ref<RavenAttachment | null>(null)
const draft = ref('')

const threadOpen = ref(false)
const threadLoading = ref(false)
const threadSending = ref(false)
const threadError = ref('')
const threadParent = ref<RavenMessage | null>(null)
const threadReplies = ref<RavenMessage[]>([])
const threadDraft = ref('')
const activeThreadId = ref('')

const FORCED_REFRESH_INTERVAL_MS = 5000
let forcedRefreshTimer: number | undefined
let forcedRefreshInFlight = false

const requestedChannel = computed(() => String(route.query.channel || '').trim())
const isAiMode = computed(() => {
  const queryMode = String(route.query.mode || '').toLowerCase()
  const metaMode = String(route.meta?.mode || '').toLowerCase()

  return queryMode === 'ai' || metaMode === 'peri' || route.path === '/chat/peri'
})

const chat = useRavenChat({
  requestedChannel,
  isAiMode,
  defaultWorkspace,
})

const activeChannelLabel = computed(() => getChannelLabel(chat.activeChannel.value))
const periAssistantLabel = computed(() => `${periBotName.value || 'PERI'} AI assistant`)
const orderedThreadReplies = computed(() => sortMessagesOldestFirst(threadReplies.value))

const realtime = useRavenRealtime({
  channelId: chat.activeChannelId,
  threadChannelId: activeThreadId,
  currentUser: chat.currentUser,
  onMessageCreated(message) {
    if (message.channel_id === activeThreadId.value) {
      mergeThreadReplies([message])
      scrollThreadToBottom()
      return
    }

    chat.mergeMessages([message])
    scrollToBottom()
  },
  onMessageEdited(messageId, patch) {
    if (!messageId) return

    if (patch.channel_id === activeThreadId.value) {
      patchThreadReply(messageId, patch)
      return
    }

    chat.patchMessage(messageId, patch)
  },
  onMessageDeleted(messageId) {
    chat.deleteMessage(messageId)
    threadReplies.value = threadReplies.value.filter((reply) => reply.name !== messageId)
  },
  onMessageReacted(messageId, reactions) {
    chat.patchMessage(messageId, { message_reactions: reactions })
    patchThreadReply(messageId, { message_reactions: reactions })
  },
  onMessageSaved(messageId, likedBy) {
    chat.patchMessage(messageId, { _liked_by: likedBy })
    patchThreadReply(messageId, { _liked_by: likedBy })
  },
  async onChannelUpdated(channelId) {
    if (channelId === chat.activeChannelId.value) {
      await chat.fetchNewer()
      await scrollToBottom()
    }

    if (channelId === activeThreadId.value) {
      await refreshThreadMessages()
    }
  },
  async onThreadReply(channelId) {
    if (channelId === activeThreadId.value) {
      await refreshThreadMessages()
    }

    await chat.fetchNewer()
  },
})

function decodeHtml(value: string) {
  if (!value) return ''

  const textarea = document.createElement('textarea')
  textarea.innerHTML = value

  return textarea.value
}

function containsHtml(value: string) {
  return /<([a-z][\w:-]*)(?:\s[^>]*)?>/i.test(value)
}

function escapeHtml(value: string) {
  const div = document.createElement('div')
  div.textContent = value
  return div.innerHTML
}

function textToHtml(value: string) {
  return escapeHtml(value)
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\n/g, '<br>')
}

function sanitiseMessageHtml(value: string) {
  if (!value) return ''

  const template = document.createElement('template')
  template.innerHTML = value

  const allowedTags = new Set([
    'A',
    'B',
    'BLOCKQUOTE',
    'BR',
    'CODE',
    'DIV',
    'EM',
    'I',
    'LI',
    'OL',
    'P',
    'PRE',
    'S',
    'SPAN',
    'STRONG',
    'U',
    'UL',
  ])

  const allowedAttributes: Record<string, Set<string>> = {
    A: new Set(['href', 'target', 'rel']),
  }

  function cleanNode(node: Node) {
    const children = Array.from(node.childNodes)

    for (const child of children) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const element = child as HTMLElement
        const tagName = element.tagName.toUpperCase()

        if (!allowedTags.has(tagName)) {
          element.replaceWith(...Array.from(element.childNodes))
          continue
        }

        for (const attribute of Array.from(element.attributes)) {
          const attrName = attribute.name.toLowerCase()
          const allowedForTag = allowedAttributes[tagName]
          const isAllowed = allowedForTag?.has(attrName) || false

          if (!isAllowed) {
            element.removeAttribute(attribute.name)
            continue
          }

          if (tagName === 'A' && attrName === 'href') {
            const href = attribute.value.trim()
            const isSafeHref = href.startsWith('/') || href.startsWith('#') || /^https?:\/\//i.test(href) || /^mailto:/i.test(href)

            if (!isSafeHref) {
              element.removeAttribute('href')
            }
          }
        }

        if (tagName === 'A') {
          element.setAttribute('target', '_blank')
          element.setAttribute('rel', 'noopener noreferrer')
        }

        cleanNode(element)
      } else if (child.nodeType === Node.COMMENT_NODE) {
        child.remove()
      }
    }
  }

  cleanNode(template.content)

  return template.innerHTML.trim()
}

function getVisibleMessageHtml(message: RavenMessage) {
  const raw = String(message.text || message.message || message.content || '').trim()

  if (!raw) return ''

  const html = containsHtml(raw) ? raw : textToHtml(decodeHtml(raw))

  return sanitiseMessageHtml(html)
}

function getInitials(value: string) {
  return value
    .split(/[ ._-]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

function formatFallbackUserName(userValue?: string) {
  if (!userValue) return ''

  if (!userValue.includes('@')) {
    return userValue
  }

  return userValue
    .split('@')[0]
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function isBotMessage(message: RavenMessage) {
  return Boolean(message.bot || message.is_bot_message)
}

function isOwnMessage(message: RavenMessage) {
  if (isBotMessage(message)) return false

  return message.owner === chat.currentUser.value || message.sender === chat.currentUser.value
}

function getMessageDisplayName(message: RavenMessage) {
  if (isBotMessage(message)) {
    return message.bot || message.sender_full_name || periBotName.value || 'AI Assistant'
  }

  if (isOwnMessage(message)) {
    return chat.currentUserFullName.value || userFullname.value || 'You'
  }

  return (
    message.sender_full_name ||
    formatFallbackUserName(message.sender || message.owner || chat.currentUser.value || user.value) ||
    'User'
  )
}

function getMessageAvatarImage(message: RavenMessage) {
  if (isBotMessage(message)) {
    return message.bot_image || ''
  }

  return message.user_image || ''
}

function getMessageInitials(message: RavenMessage) {
  return getInitials(getMessageDisplayName(message) || 'User')
}

function formatMessageTime(value?: string) {
  if (!value) return ''

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function getAttachmentExtension(attachment: RavenAttachment) {
  if (attachment.extension) {
    return attachment.extension.toLowerCase()
  }

  const fileName = attachment.file_name || attachment.file_url || ''

  if (!fileName.includes('.')) {
    return 'file'
  }

  return fileName.split('?')[0].split('#')[0].split('.').pop()?.toLowerCase() || 'file'
}

function getAttachmentLabel(attachment: RavenAttachment) {
  const extension = getAttachmentExtension(attachment)

  if (extension.length > 5) {
    return 'file'
  }

  return extension || 'file'
}

function isImageAttachment(attachment: RavenAttachment) {
  const extension = getAttachmentExtension(attachment)

  return Boolean(attachment.is_image) || [
    'jpg',
    'jpeg',
    'png',
    'gif',
    'webp',
    'bmp',
    'svg',
  ].includes(extension)
}

function isPdfAttachment(attachment: RavenAttachment) {
  const extension = getAttachmentExtension(attachment)

  return Boolean(attachment.is_pdf) || extension === 'pdf'
}

function canIframePreview(attachment: RavenAttachment) {
  const extension = getAttachmentExtension(attachment)

  return isPdfAttachment(attachment) || [
    'txt',
    'csv',
    'json',
    'md',
    'log',
  ].includes(extension)
}

function formatFileSize(size: number) {
  if (!size) return 'File'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function getThreadCount(message: RavenMessage) {
  return Number(
    message.number_of_replies ??
      message.thread_count ??
      message.reply_count ??
      message.replies_count ??
      message.thread_replies_count ??
      0
  ) || 0
}

function shouldShowThreadButton(message: RavenMessage) {
  return Boolean(message.is_thread) || getThreadCount(message) > 0
}

function getThreadButtonLabel(message: RavenMessage) {
  const count = getThreadCount(message)
  return count ? `Open thread · ${count}` : 'Open thread'
}

function scrollElementToBottom(element: HTMLElement | null) {
  if (!element) return
  element.scrollTop = element.scrollHeight
}

async function scrollToBottom() {
  await nextTick()

  requestAnimationFrame(() => {
    scrollElementToBottom(messagesEl.value)

    requestAnimationFrame(() => {
      scrollElementToBottom(messagesEl.value)
    })
  })
}

async function scrollThreadToBottom() {
  await nextTick()

  requestAnimationFrame(() => {
    scrollElementToBottom(threadMessagesEl.value)

    requestAnimationFrame(() => {
      scrollElementToBottom(threadMessagesEl.value)
    })
  })
}

function openPreview(attachment: RavenAttachment) {
  previewAttachment.value = attachment
}

function closePreview() {
  previewAttachment.value = null
}

function openFilePicker() {
  fileInputEl.value?.click()
}

async function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) return

  const message = await chat.uploadFile(file, draft.value.trim())
  draft.value = ''
  input.value = ''

  if (message) {
    await scrollToBottom()
  }
}

async function sendDraft() {
  const text = draft.value.trim()
  if (!text) return

  const sent = await chat.sendText(text)

  if (sent) {
    draft.value = ''
    await scrollToBottom()
  }
}

function mergeThreadReplies(incoming: RavenMessage[]) {
  if (!incoming.length) return

  const byName = new Map<string, RavenMessage>()

  for (const message of threadReplies.value) {
    byName.set(message.name, message)
  }

  for (const raw of incoming) {
    const message = normaliseRavenMessage(raw)
    const existing = byName.get(message.name)
    byName.set(message.name, existing ? { ...existing, ...message } : message)
  }

  threadReplies.value = sortMessagesOldestFirst([...byName.values()])
}

function patchThreadReply(messageId: string, patch: Partial<RavenMessage>) {
  if (!messageId) return

  threadReplies.value = threadReplies.value.map((reply) => {
    if (reply.name !== messageId) return reply
    return normaliseRavenMessage({ ...reply, ...patch })
  })
}

async function refreshThreadMessages() {
  if (!activeThreadId.value) return

  try {
    const data = await getMessages(activeThreadId.value, 50)
    threadReplies.value = data.messages
    await scrollThreadToBottom()
  } catch (err) {
    threadError.value = err instanceof Error ? err.message : 'Could not refresh Raven thread.'
  }
}

async function openThread(message: RavenMessage) {
  threadOpen.value = true
  threadLoading.value = true
  threadError.value = ''
  threadParent.value = message
  threadReplies.value = []
  threadDraft.value = ''

  try {
    let threadId = message.is_thread ? message.name : ''

    if (!threadId) {
      const existing = await getExistingMessageThread(message.name)
      threadId = existing.thread_id || ''
      threadParent.value = existing.parent || message
      threadReplies.value = sortMessagesOldestFirst(existing.replies || [])
    }

    if (!threadId) {
      const createdOrLoaded = await getMessageThread(message.name)
      threadId = createdOrLoaded.thread_id || ''
      threadParent.value = createdOrLoaded.parent || message
      threadReplies.value = sortMessagesOldestFirst(createdOrLoaded.replies || [])
    }

    activeThreadId.value = threadId
    realtime.subscribeChannelDoc(threadId)

    if (threadId && !threadReplies.value.length) {
      await refreshThreadMessages()
    }
  } catch (err) {
    threadError.value = err instanceof Error ? err.message : 'Could not open Raven thread.'
  } finally {
    threadLoading.value = false
    await scrollThreadToBottom()
  }
}

function closeThread() {
  threadOpen.value = false
  activeThreadId.value = ''
  threadParent.value = null
  threadReplies.value = []
  threadDraft.value = ''
  threadError.value = ''
}

async function sendThreadReply() {
  const text = threadDraft.value.trim()
  if (!text || !activeThreadId.value || threadSending.value) return

  threadSending.value = true
  threadError.value = ''

  try {
    const message = await sendTextMessage({
      channelId: activeThreadId.value,
      text,
    })

    mergeThreadReplies([message])
    threadDraft.value = ''
    await scrollThreadToBottom()
    await chat.fetchNewer()
  } catch (err) {
    threadError.value = err instanceof Error ? err.message : 'Could not send Raven thread reply.'
  } finally {
    threadSending.value = false
  }
}


function getLatestMessageName(items: RavenMessage[]) {
  const ordered = sortMessagesOldestFirst(items || [])
  return ordered[ordered.length - 1]?.name || ''
}

async function forcedRefreshFromRaven() {
  if (forcedRefreshInFlight || chat.loading.value || !chat.activeChannelId.value) {
    return
  }

  forcedRefreshInFlight = true

  const beforeLatestMessage = getLatestMessageName(chat.messages.value)
  const beforeThreadLatestMessage = getLatestMessageName(threadReplies.value)

  try {
    await chat.loadMessages()

    const afterLatestMessage = getLatestMessageName(chat.messages.value)

    if (afterLatestMessage && afterLatestMessage !== beforeLatestMessage) {
      await scrollToBottom()
    }

    if (threadOpen.value && activeThreadId.value) {
      await refreshThreadMessages()

      const afterThreadLatestMessage = getLatestMessageName(threadReplies.value)

      if (afterThreadLatestMessage && afterThreadLatestMessage !== beforeThreadLatestMessage) {
        await scrollThreadToBottom()
      }
    }
  } catch (err) {
    console.warn('[verto raven polling] forced refresh failed', err)
  } finally {
    forcedRefreshInFlight = false
  }
}

function startForcedRefreshPolling() {
  stopForcedRefreshPolling()

  console.log('[verto raven polling] started', {
    intervalMs: FORCED_REFRESH_INTERVAL_MS,
    activeChannel: chat.activeChannelId.value,
  })

  forcedRefreshTimer = window.setInterval(() => {
    forcedRefreshFromRaven()
  }, FORCED_REFRESH_INTERVAL_MS)
}

function stopForcedRefreshPolling() {
  if (forcedRefreshTimer) {
    window.clearInterval(forcedRefreshTimer)
    forcedRefreshTimer = undefined
  }
}

async function handlePeriAutoSend() {
  const auto = String(route.query.auto || '')
  if (auto !== 'analyse') return

  const message = sessionStorage.getItem('verto_peri_autosend_message')
  if (!message) return

  sessionStorage.removeItem('verto_peri_autosend_message')
  sessionStorage.removeItem('verto_peri_source_project')

  draft.value = message
  await nextTick()
  await sendDraft()

  const query = { ...route.query }
  delete query.auto
  await router.replace({ path: route.path, query })
}

async function reloadChat() {
  await chat.load()
  realtime.resubscribeAll()
  startForcedRefreshPolling()
  await scrollToBottom()
}

watch(
  () => route.fullPath,
  async () => {
    await chat.load()
    realtime.resubscribeAll()
    startForcedRefreshPolling()
    await handlePeriAutoSend()
    await scrollToBottom()
  }
)

onMounted(async () => {
  await loadMobileBoot()
  await chat.load()
  realtime.start()
  startForcedRefreshPolling()
  await handlePeriAutoSend()
  await scrollToBottom()
})

onBeforeUnmount(() => {
  stopForcedRefreshPolling()
  realtime.stop()
})
</script>

<style scoped>
.rich-message-html :deep(p) {
  margin: 0 0 0.35rem;
}

.rich-message-html :deep(p:last-child) {
  margin-bottom: 0;
}

.rich-message-html :deep(ul),
.rich-message-html :deep(ol) {
  margin: 0.35rem 0 0.35rem 1rem;
  padding: 0;
}

.rich-message-html :deep(li) {
  margin: 0.15rem 0;
}

.rich-message-html :deep(a) {
  text-decoration: underline;
}

.rich-message-html :deep(pre) {
  margin: 0.35rem 0;
  overflow-x: auto;
  border-radius: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.08);
}

.rich-message-html :deep(code) {
  border-radius: 0.25rem;
  padding: 0.05rem 0.25rem;
  background: rgba(0, 0, 0, 0.08);
}
</style>
