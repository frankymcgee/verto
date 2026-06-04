<template>
  <section class="min-h-screen bg-surface-gray-1">
    <main class="flex h-[calc(100vh-3.5rem-var(--mobile-bottom-tabs-height,4rem))] flex-col">
      <div
        v-if="loading"
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
        v-else-if="error"
        class="p-3"
      >
        <Card class="border border-red-200 bg-red-50 p-3">
          <p class="text-sm font-medium text-red-800">
            Could not load chat
          </p>

          <p class="mt-1 text-sm text-red-700">
            {{ error }}
          </p>

          <Button
            variant="solid"
            theme="gray"
            class="mt-3 w-full justify-center"
            @click="loadChat"
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
                {{ activeChannel ? getChannelLabel(activeChannel) : 'Chat' }}
              </p>

              <p
                v-if="isAiMode"
                class="truncate text-xs text-blue-600"
              >
                {{ periAssistantLabel }}
              </p>

              <p
                v-else-if="activeChannel?.description"
                class="truncate text-xs text-ink-gray-5"
              >
                {{ activeChannel.description }}
              </p>

              <p
                v-else
                class="truncate text-xs text-ink-gray-5"
              >
                {{ orderedMessages.length }} {{ orderedMessages.length === 1 ? 'message' : 'messages' }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-1 text-[11px] text-ink-gray-5">
              <span
                class="h-2 w-2 rounded-full"
                :class="realtimeReady ? 'bg-green-500' : 'bg-amber-500'"
              />
              <span>{{ realtimeStatus }}</span>
            </div>
          </div>
        </div>

        <div
          ref="messagesEl"
          class="flex-1 space-y-3 overflow-y-auto px-3 py-3"
        >
          <Card
            v-if="!activeChannel"
            class="p-4"
          >
            <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center">
              <p class="text-sm font-medium text-ink-gray-7">
                No channel selected.
              </p>

              <p class="mt-1 text-sm text-ink-gray-5">
                Choose a channel above to start chatting.
              </p>
            </div>
          </Card>

          <Card
            v-else-if="orderedMessages.length === 0"
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
            v-for="message in orderedMessages"
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
                v-if="getVisibleMessageText(message)"
                class="whitespace-pre-wrap break-words text-sm leading-relaxed"
                :class="isOwnMessage(message) ? 'text-white' : 'text-ink-gray-8'"
              >
                {{ getVisibleMessageText(message) }}
              </div>

              <!-- Raven Document Previews -->
              <div
                v-if="getDocumentPreviewsForMessage(message).length"
                class="mt-2 space-y-2"
              >
                <button
                  v-for="preview in getDocumentPreviewsForMessage(message)"
                  :key="getDocumentPreviewKey(preview.doctype, preview.docname)"
                  type="button"
                  class="w-full overflow-hidden rounded-lg border text-left"
                  :class="isOwnMessage(message)
                    ? 'border-white/20 bg-white/15'
                    : 'border-outline-gray-2 bg-surface-gray-1'"
                  @click="openDocumentPreview(preview)"
                >
                  <div
                    v-if="preview.preview_image"
                    class="h-28 w-full overflow-hidden border-b"
                    :class="isOwnMessage(message) ? 'border-white/10' : 'border-outline-gray-1'"
                  >
                    <img
                      :src="preview.preview_image"
                      :alt="preview.title || preview.docname"
                      class="h-full w-full object-cover"
                      loading="lazy"
                      @load="scrollToBottom"
                    />
                  </div>

                  <div class="p-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div
                          class="mb-1 inline-flex rounded px-1.5 py-0.5 text-[11px] font-medium"
                          :class="isOwnMessage(message)
                            ? 'bg-white/20 text-white'
                            : 'bg-indigo-50 text-indigo-700'"
                        >
                          {{ preview.doctype }}
                        </div>

                        <p
                          class="truncate text-sm font-semibold"
                          :class="isOwnMessage(message) ? 'text-white' : 'text-ink-gray-9'"
                        >
                          {{ preview.title || preview.id || preview.docname }}
                        </p>

                        <p
                          v-if="preview.id && preview.id !== preview.title"
                          class="mt-0.5 truncate text-xs"
                          :class="isOwnMessage(message) ? 'text-white/70' : 'text-ink-gray-5'"
                        >
                          {{ preview.id }}
                        </p>
                      </div>

                      <span
                        class="shrink-0 text-sm"
                        :class="isOwnMessage(message) ? 'text-white/70' : 'text-ink-gray-5'"
                      >
                        ↗
                      </span>
                    </div>

                    <div
                      v-if="preview.fields?.length"
                      class="mt-3 space-y-1.5"
                    >
                      <div
                        v-for="field in preview.fields"
                        :key="field.label"
                        class="grid grid-cols-[104px_1fr] gap-2 text-xs"
                      >
                        <span
                          class="font-semibold"
                          :class="isOwnMessage(message) ? 'text-white/70' : 'text-ink-gray-5'"
                        >
                          {{ field.label }}
                        </span>

                        <span
                          class="break-words"
                          :class="isOwnMessage(message) ? 'text-white' : 'text-ink-gray-8'"
                        >
                          {{ field.value }}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              </div>

              <!-- File Attachments -->
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
                    />
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
                  v-if="shouldShowThreadButton"
                  type="button"
                  class="rounded-full px-2.5 py-1 text-[11px] font-semibold"
                  :class="isOwnMessage(message)
                    ? 'bg-white/15 text-white'
                    : 'bg-blue-50 text-blue-700'"
                  @click="openThread(message)"
                >
                  {{ message.thread_count ? `Open thread · ${message.thread_count}` : 'Open thread' }}
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
          @submit.prevent="sendMessage"
        >
          <div class="flex items-end gap-2">
            <Textarea
              v-model="draft"
              class="min-w-0 flex-1"
              placeholder="Message"
              :rows="1"
              :disabled="sending || !activeChannel"
              @keydown.enter.exact.prevent="sendMessage"
            />

            <Button
              type="submit"
              variant="solid"
              theme="gray"
              :loading="sending"
              :disabled="sending || !activeChannel || !draft.trim()"
            >
              Send
            </Button>
          </div>

          <p
            v-if="composerError"
            class="mt-2 text-sm text-red-600"
          >
            {{ composerError }}
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
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
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
          />

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

        <div class="border-t border-outline-gray-1 bg-surface-white p-3">
          <Button
            as="a"
            :href="previewAttachment.file_url"
            target="_blank"
            rel="noopener noreferrer"
            variant="subtle"
            theme="gray"
            class="w-full justify-center"
          >
            Open original
          </Button>
        </div>
      </Card>
    </div>

    <!-- Thread Drawer - Ask PERI Only -->
    <div
      v-if="threadOpen"
      class="fixed inset-0 z-[65] flex items-end bg-black/50"
      @click.self="closeThread"
    >
      <Card class="flex max-h-[88vh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white">
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
          <div class="min-w-0">
            <p class="truncate text-base font-semibold text-ink-gray-9">
              {{ periBotName }} Thread
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
              <div class="flex gap-2">
                <Avatar
                  :image="threadParent.user_image"
                  :label="getInitials(threadParent.sender_full_name || threadParent.owner || 'User')"
                  size="sm"
                  class="mt-1 shrink-0"
                />

                <div class="min-w-0 flex-1">
                  <p class="text-xs font-semibold text-ink-gray-7">
                    {{ threadParent.sender_full_name || formatFallbackUserName(threadParent.owner) }}
                  </p>

                  <p
                    v-if="getVisibleMessageText(threadParent)"
                    class="mt-1 whitespace-pre-wrap break-words text-sm text-ink-gray-8"
                  >
                    {{ getVisibleMessageText(threadParent) }}
                  </p>
                </div>
              </div>
            </Card>

            <div
              v-if="orderedThreadReplies.length"
              class="space-y-2"
            >
              <div
                v-for="reply in orderedThreadReplies"
                :key="reply.name"
                class="flex gap-2"
                :class="isOwnMessage(reply) ? 'justify-end' : 'justify-start'"
              >
                <Avatar
                  v-if="!isOwnMessage(reply)"
                  :image="getMessageAvatarImage(reply)"
                  :label="getMessageInitials(reply)"
                  size="sm"
                  class="mt-1 shrink-0"
                />

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

                  <p
                    v-if="getVisibleMessageText(reply)"
                    class="whitespace-pre-wrap break-words text-sm leading-relaxed"
                    :class="isOwnMessage(reply) ? 'text-white' : 'text-ink-gray-8'"
                  >
                    {{ getVisibleMessageText(reply) }}
                  </p>

                  <div
                    class="mt-1 text-[11px]"
                    :class="isOwnMessage(reply) ? 'text-white/75' : 'text-ink-gray-5'"
                  >
                    {{ formatMessageTime(reply.creation) }}
                  </div>
                </div>

                <Avatar
                  v-if="isOwnMessage(reply)"
                  :image="getMessageAvatarImage(reply)"
                  :label="getMessageInitials(reply)"
                  size="sm"
                  class="mt-1 shrink-0"
                />
              </div>
            </div>

            <Card
              v-else
              class="p-3"
            >
              <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-5 text-center">
                <p class="text-sm font-medium text-ink-gray-7">
                  No replies yet.
                </p>

                <p class="mt-1 text-sm text-ink-gray-5">
                  Start the thread with a reply.
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
          class="border-t border-outline-gray-1 bg-surface-white p-3"
          @submit.prevent="sendThreadReply"
        >
          <div class="flex items-end gap-2">
            <Textarea
              v-model="threadDraft"
              class="min-w-0 flex-1"
              :placeholder="`Reply to ${periBotName} thread`"
              :rows="1"
              :disabled="threadSending || !threadParent"
              @keydown.enter.exact.prevent="sendThreadReply"
            />

            <Button
              type="submit"
              variant="solid"
              theme="gray"
              :loading="threadSending"
              :disabled="threadSending || !threadParent || !threadDraft.trim()"
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
import { useRoute } from 'vue-router'
import {
  Avatar,
  Button,
  Card,
  Textarea,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { useMobileBoot } from '../lib/mobileBoot'

type FrappeResponse<T> = {
  message: T
}

type RavenChannel = {
  name: string
  channel_name?: string
  channel_id?: string
  workspace?: string
  type?: string
  description?: string
  is_direct_message?: boolean
}

type RavenAttachment = {
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

type RavenPreviewField = {
  label: string
  value: string | number | null
}

type RavenDocumentPreview = {
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

type DocumentLink = {
  doctype: string
  docname: string
}

type RavenMessage = {
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
  attachments?: RavenAttachment[]
  thread_count?: number
  is_thread?: boolean
  link_doctype?: string
  link_document?: string
  document_links?: DocumentLink[]
  document_preview?: RavenDocumentPreview | null
  linked_doctype?: string
  linked_docname?: string
  reference_doctype?: string
  reference_docname?: string
  document_type?: string
  document_name?: string
}

type ChatBootstrap = {
  current_user: string
  current_user_full_name?: string
  channels: RavenChannel[]
  active_channel?: RavenChannel | null
  messages: RavenMessage[]
}

type MessagesPayload = {
  messages: RavenMessage[]
}

type SendMessagePayload = {
  message: RavenMessage
}

type ThreadPayload = {
  parent: RavenMessage
  replies: RavenMessage[]
  thread_supported?: boolean
  thread_id?: string
}

type SendThreadReplyPayload = {
  reply: RavenMessage
  thread_id?: string
}

const route = useRoute()

const {
  loadMobileBoot,
  defaultChatChannel,
  defaultWorkspace,
  periBotName,
  periBotUser,
  user,
  userFullname,
} = useMobileBoot()

const loading = ref(true)
const refreshing = ref(false)
const sending = ref(false)
const error = ref('')
const composerError = ref('')

const currentUser = ref('')
const currentUserFullName = ref('')
const channels = ref<RavenChannel[]>([])
const activeChannel = ref<RavenChannel | null>(null)
const messages = ref<RavenMessage[]>([])
const draft = ref('')

const messagesEl = ref<HTMLElement | null>(null)
const threadMessagesEl = ref<HTMLElement | null>(null)
const previewAttachment = ref<RavenAttachment | null>(null)

const realtimeReady = ref(false)
const realtimeStatus = ref('Connecting')

const threadOpen = ref(false)
const threadLoading = ref(false)
const threadSending = ref(false)
const threadError = ref('')
const threadParent = ref<RavenMessage | null>(null)
const threadReplies = ref<RavenMessage[]>([])
const threadDraft = ref('')
const activeThreadId = ref('')

const fetchingNewer = ref(false)
const fetchingThread = ref(false)

const activeChannelName = computed(() => {
  return activeChannel.value?.name || activeChannel.value?.channel_id || ''
})

const isAiMode = computed(() => {
  const queryMode = String(route.query.mode || '').toLowerCase()
  const metaMode = String(route.meta?.mode || '').toLowerCase()

  return queryMode === 'ai' || metaMode === 'peri' || route.path === '/chat/peri'
})

const periAssistantLabel = computed(() => {
  const name = periBotName.value || 'PERI'

  return `${name} AI assistant`
})

const shouldShowThreadButton = computed(() => {
  return isAiMode.value
})

const orderedMessages = computed(() => {
  return sortMessagesOldestFirst(messages.value)
})

const orderedThreadReplies = computed(() => {
  return sortMessagesOldestFirst(threadReplies.value)
})

function sortMessagesOldestFirst(items: RavenMessage[]) {
  return [...items].sort((a, b) => {
    const aTime = new Date(a.creation || '').getTime()
    const bTime = new Date(b.creation || '').getTime()

    if (Number.isFinite(aTime) && Number.isFinite(bTime) && aTime !== bTime) {
      return aTime - bTime
    }

    return String(a.name || '').localeCompare(String(b.name || ''))
  })
}

function getChannelLabel(channel: RavenChannel) {
  return channel.channel_name || channel.name || channel.channel_id || 'Channel'
}

function getChannelKeys(channel: RavenChannel) {
  return [
    channel.name,
    channel.channel_name,
    channel.channel_id,
  ]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase())
}

function isActiveChannel(channel: RavenChannel) {
  if (!activeChannel.value) {
    return false
  }

  const activeKeys = getChannelKeys(activeChannel.value)
  const channelKeys = getChannelKeys(channel)

  return channelKeys.some((key) => activeKeys.includes(key))
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

function decodeHtml(value: string) {
  if (!value) return ''

  const textarea = document.createElement('textarea')
  textarea.innerHTML = value

  return textarea.value
}

function stripHtml(value: string) {
  return decodeHtml(value)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .trim()
}

function getRawMessageText(message: RavenMessage) {
  const text = message.content || message.text || ''
  const alternate = message.message || ''

  if (text && alternate && stripHtml(text) === stripHtml(alternate)) {
    return text
  }

  if (text && alternate) {
    return `${text}\n${alternate}`
  }

  return text || alternate || ''
}

function getVisibleMessageText(message: RavenMessage) {
  let text = stripHtml(getRawMessageText(message))

  for (const link of extractDocumentLinks(message)) {
    const encodedDoctypePlus = encodeURIComponent(link.doctype).replace(/%20/g, '+')
    const encodedDoctype = encodeURIComponent(link.doctype)
    const encodedDocname = encodeURIComponent(link.docname)
    const slug = doctypeToSlug(link.doctype)

    text = text
      .replace(new RegExp(`\\/?api\\/method\\/raven\\.api\\.document_link\\.get_preview_data\\?doctype=${escapeRegExp(encodedDoctypePlus)}&docname=${escapeRegExp(encodedDocname)}`, 'gi'), '')
      .replace(new RegExp(`\\/?api\\/method\\/raven\\.api\\.document_link\\.get_preview_data\\?doctype=${escapeRegExp(encodedDoctype)}&docname=${escapeRegExp(encodedDocname)}`, 'gi'), '')
      .replace(new RegExp(`\\/?app\\/${escapeRegExp(slug)}\\/${escapeRegExp(link.docname)}`, 'gi'), '')
  }

  return text
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
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

function formatFileSize(size: number) {
  if (!size) return 'File'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function getAttachmentExtension(attachment: RavenAttachment) {
  if (attachment.extension) {
    return attachment.extension.toLowerCase()
  }

  const fileName = attachment.file_name || attachment.file_url || ''

  if (!fileName.includes('.')) {
    return 'file'
  }

  return fileName.split('.').pop()?.toLowerCase() || 'file'
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

function isBotMessage(message: RavenMessage) {
  return Boolean(message.bot)
}

function isUserMessage(message: RavenMessage) {
  if (isBotMessage(message)) {
    return false
  }

  return message.owner === currentUser.value || message.sender === currentUser.value
}

function isOwnMessage(message: RavenMessage) {
  return isUserMessage(message)
}

function getMessageDisplayName(message: RavenMessage) {
  if (isBotMessage(message)) {
    return message.bot || message.sender_full_name || periBotName.value || 'AI Assistant'
  }

  return (
    message.sender_full_name ||
    currentUserFullName.value ||
    userFullname.value ||
    formatFallbackUserName(message.sender || message.owner || currentUser.value || user.value) ||
    'You'
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

function doctypeToSlug(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function getDocumentPreviewKey(doctype: string, docname: string) {
  return `${doctype}::${docname}`
}

function extractDocumentLinks(message: RavenMessage): DocumentLink[] {
  const links: DocumentLink[] = []

  if (message.link_doctype && message.link_document) {
    links.push({
      doctype: message.link_doctype,
      docname: message.link_document,
    })
  }

  if (Array.isArray(message.document_links)) {
    links.push(...message.document_links)
  }

  const possiblePairs = [
    [message.linked_doctype, message.linked_docname],
    [message.reference_doctype, message.reference_docname],
    [message.document_type, message.document_name],
  ]

  for (const [doctype, docname] of possiblePairs) {
    if (doctype && docname) {
      links.push({
        doctype,
        docname,
      })
    }
  }

  return links.filter((link, index, self) => {
    return index === self.findIndex((item) => {
      return item.doctype === link.doctype && item.docname === link.docname
    })
  })
}

function getDocumentPreviewsForMessage(message: RavenMessage): RavenDocumentPreview[] {
  const previews: RavenDocumentPreview[] = []

  if (message.document_preview) {
    previews.push(normaliseDocumentPreview(
      message.link_doctype ||
        message.document_preview.doctype ||
        message.linked_doctype ||
        'Document',
      message.link_document ||
        message.document_preview.docname ||
        message.linked_docname ||
        message.document_preview.id ||
        '',
      message.document_preview
    ))
  }

  for (const link of extractDocumentLinks(message)) {
    if (previews.some((preview) => preview.doctype === link.doctype && preview.docname === link.docname)) {
      continue
    }

    previews.push({
      doctype: link.doctype,
      docname: link.docname,
      title: link.docname,
      subtitle: link.doctype,
      route: `/app/${doctypeToSlug(link.doctype)}/${encodeURIComponent(link.docname)}`,
      fields: [],
    })
  }

  return previews
}

function normaliseDocumentPreview(
  doctype: string,
  docname: string,
  preview: RavenDocumentPreview | any
): RavenDocumentPreview {
  const raw = preview.raw && typeof preview.raw === 'object'
    ? preview.raw
    : preview

  return {
    doctype: preview.doctype || doctype,
    docname: preview.docname || docname || preview.id || raw.id || '',
    title: preview.title || raw.preview_title || raw.title || raw.id || docname,
    subtitle: preview.subtitle || preview.doctype || doctype,
    route: preview.route || raw.raven_document_link || raw.route || raw.url,
    preview_image: preview.preview_image || raw.preview_image || null,
    id: preview.id || raw.id || docname,
    fields: normalisePreviewFields(preview),
    raw,
  }
}

function normalisePreviewFields(preview: RavenDocumentPreview | any): RavenPreviewField[] {
  if (Array.isArray(preview.fields) && preview.fields.length) {
    return preview.fields
      .map((field: any) => ({
        label: field.label || field.fieldname || field.key || '',
        value: field.value ?? field.display_value ?? field.formatted_value ?? '',
      }))
      .filter((field: RavenPreviewField) => field.label && field.value !== null && field.value !== undefined && String(field.value) !== '')
  }

  const raw = preview.raw && typeof preview.raw === 'object'
    ? preview.raw
    : preview

  return Object.entries(raw || {})
    .filter(([key, value]) => {
      return ![
        'preview_image',
        'preview_title',
        'id',
        'raven_document_link',
        'doctype',
        'docname',
        'title',
        'subtitle',
        'route',
        'url',
        'raw',
        'fields',
      ].includes(key) && value !== null && value !== undefined && String(value) !== ''
    })
    .map(([label, value]) => ({
      label,
      value: value as string | number | null,
    }))
}

function openDocumentPreview(preview: RavenDocumentPreview) {
  window.location.href = preview.route ||
    `/app/${doctypeToSlug(preview.doctype)}/${encodeURIComponent(preview.docname)}`
}

function findChannelByRequestedValue(requestedChannel: string) {
  const requested = requestedChannel.toLowerCase()

  return channels.value.find((channel) => {
    return getChannelKeys(channel).includes(requested)
  })
}

function getRequestedRouteChannel() {
  const queryChannel = String(route.query.channel || '').trim()

  if (queryChannel) {
    return queryChannel
  }

  if (!isAiMode.value && defaultChatChannel.value) {
    return defaultChatChannel.value
  }

  return ''
}

async function selectRequestedRouteChannel() {
  const requestedChannel = getRequestedRouteChannel()

  if (!requestedChannel) {
    return
  }

  const queryChannel = findChannelByRequestedValue(requestedChannel)

  if (!queryChannel) {
    activeChannel.value = {
      name: requestedChannel,
      channel_name: requestedChannel,
      channel_id: requestedChannel,
      workspace: defaultWorkspace.value,
    }

    messages.value = []
    await loadMessages()
    return
  }

  if (isActiveChannel(queryChannel)) {
    return
  }

  activeChannel.value = queryChannel
  messages.value = []
  await loadMessages()
}

function selectChannel(channel: RavenChannel) {
  activeChannel.value = channel
  messages.value = []
  loadMessages()
}

function scrollElementToBottom(element: HTMLElement | null) {
  if (!element) {
    return
  }

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

function mergeMessages(incoming: RavenMessage[]) {
  if (!incoming.length) {
    return
  }

  const byName = new Map<string, RavenMessage>()

  for (const message of messages.value) {
    byName.set(message.name, message)
  }

  for (const message of incoming) {
    byName.set(message.name, message)
  }

  messages.value = sortMessagesOldestFirst([...byName.values()])
}

function mergeThreadReplies(incoming: RavenMessage[]) {
  if (!incoming.length) {
    return
  }

  const byName = new Map<string, RavenMessage>()

  for (const message of threadReplies.value) {
    byName.set(message.name, message)
  }

  for (const message of incoming) {
    byName.set(message.name, message)
  }

  threadReplies.value = sortMessagesOldestFirst([...byName.values()])
}

function getNewestMessageName(items: RavenMessage[]) {
  const sorted = sortMessagesOldestFirst(items)

  return sorted[sorted.length - 1]?.name || ''
}

async function loadChat() {
  loading.value = true
  error.value = ''
  composerError.value = ''

  try {
    await loadMobileBoot()

    const data = await apiRequest<FrappeResponse<ChatBootstrap>>(
      '/api/method/verto.api.mobile.raven.get_mobile_chat_bootstrap'
    )

    currentUser.value = data.message.current_user || user.value || ''
    currentUserFullName.value = data.message.current_user_full_name || userFullname.value || ''
    channels.value = data.message.channels || []

    const requestedChannel = getRequestedRouteChannel()
    const queryChannel = requestedChannel
      ? findChannelByRequestedValue(requestedChannel)
      : null

    activeChannel.value = queryChannel ||
      data.message.active_channel ||
      channels.value[0] ||
      null

    if (requestedChannel && !queryChannel && activeChannel.value?.name !== requestedChannel) {
      activeChannel.value = {
        name: requestedChannel,
        channel_name: requestedChannel,
        channel_id: requestedChannel,
        workspace: defaultWorkspace.value,
      }
    }

    if (activeChannel.value) {
      if (requestedChannel || activeChannel.value.name !== data.message.active_channel?.name) {
        await loadMessages()
      } else {
        messages.value = sortMessagesOldestFirst(data.message.messages || [])
      }
    } else {
      messages.value = []
    }

    await scrollToBottom()
    setupRealtimeListeners()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load chat.'
  } finally {
    loading.value = false
  }
}

async function loadMessages() {
  if (!activeChannelName.value) {
    return
  }

  refreshing.value = true
  composerError.value = ''

  try {
    const payload = new FormData()

    payload.append('channel', activeChannelName.value)

    const data = await apiRequest<FrappeResponse<MessagesPayload>>(
      '/api/method/verto.api.mobile.raven.get_channel_messages',
      {
        method: 'POST',
        body: payload,
      }
    )

    messages.value = sortMessagesOldestFirst(data.message.messages || [])

    await scrollToBottom()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    composerError.value = err instanceof Error ? err.message : 'Could not refresh messages.'
  } finally {
    refreshing.value = false
  }
}

async function fetchNewerMessages() {
  if (!activeChannelName.value || fetchingNewer.value) {
    return
  }

  const fromMessage = getNewestMessageName(messages.value)

  if (!fromMessage) {
    await loadMessages()
    return
  }

  fetchingNewer.value = true

  try {
    const payload = new FormData()

    payload.append('channel', activeChannelName.value)
    payload.append('from_message', fromMessage)

    const data = await apiRequest<FrappeResponse<MessagesPayload>>(
      '/api/method/verto.api.mobile.raven.get_newer_messages',
      {
        method: 'POST',
        body: payload,
      }
    )

    mergeMessages(data.message.messages || [])
    await scrollToBottom()
  } catch {
    await loadMessages()
  } finally {
    fetchingNewer.value = false
  }
}

async function fetchThreadMessages() {
  if (!activeThreadId.value || fetchingThread.value) {
    return
  }

  fetchingThread.value = true

  try {
    const payload = new FormData()

    payload.append('thread_id', activeThreadId.value)

    const data = await apiRequest<FrappeResponse<MessagesPayload>>(
      '/api/method/verto.api.mobile.raven.get_thread_messages',
      {
        method: 'POST',
        body: payload,
      }
    )

    threadReplies.value = sortMessagesOldestFirst(data.message.messages || [])
    await scrollThreadToBottom()
  } catch {
    // Keep the current thread view as-is if live fetch fails.
  } finally {
    fetchingThread.value = false
  }
}

async function sendMessage() {
  const text = draft.value.trim()

  if (!text || !activeChannelName.value || sending.value) {
    return
  }

  sending.value = true
  composerError.value = ''

  try {
    const payload = new FormData()

    payload.append('channel', activeChannelName.value)
    payload.append('text', text)

    const data = await apiRequest<FrappeResponse<SendMessagePayload>>(
      '/api/method/verto.api.mobile.raven.send_channel_message',
      {
        method: 'POST',
        body: payload,
      }
    )

    draft.value = ''

    if (data.message.message) {
      mergeMessages([data.message.message])
    } else {
      await fetchNewerMessages()
    }

    await scrollToBottom()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    composerError.value = err instanceof Error ? err.message : 'Could not send message.'
  } finally {
    sending.value = false
  }
}

function openPreview(attachment: RavenAttachment) {
  previewAttachment.value = attachment
}

function closePreview() {
  previewAttachment.value = null
}

async function openThread(message: RavenMessage) {
  if (!shouldShowThreadButton.value) {
    return
  }

  threadOpen.value = true
  threadLoading.value = true
  threadError.value = ''
  threadParent.value = message
  threadReplies.value = []
  threadDraft.value = ''
  activeThreadId.value = ''

  try {
    const payload = new FormData()

    payload.append('message', message.name)

    const data = await apiRequest<FrappeResponse<ThreadPayload>>(
      '/api/method/verto.api.mobile.raven.get_message_thread',
      {
        method: 'POST',
        body: payload,
      }
    )

    threadParent.value = data.message.parent || message
    threadReplies.value = sortMessagesOldestFirst(data.message.replies || [])
    activeThreadId.value = data.message.thread_id || ''

    if (data.message.thread_supported === false) {
      threadError.value = 'Threads are not supported by this Raven message schema yet.'
    }
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    threadError.value = err instanceof Error ? err.message : 'Could not load thread.'
  } finally {
    threadLoading.value = false
    await scrollThreadToBottom()
  }
}

function closeThread() {
  threadOpen.value = false
  threadLoading.value = false
  threadSending.value = false
  threadError.value = ''
  threadParent.value = null
  threadReplies.value = []
  threadDraft.value = ''
  activeThreadId.value = ''
}

async function sendThreadReply() {
  const text = threadDraft.value.trim()

  if (!threadParent.value || !text || threadSending.value) {
    return
  }

  threadSending.value = true
  threadError.value = ''

  try {
    const payload = new FormData()

    payload.append('parent_message', threadParent.value.name)
    payload.append('text', text)

    const data = await apiRequest<FrappeResponse<SendThreadReplyPayload>>(
      '/api/method/verto.api.mobile.raven.send_thread_reply',
      {
        method: 'POST',
        body: payload,
      }
    )

    threadDraft.value = ''

    if (data.message.thread_id) {
      activeThreadId.value = data.message.thread_id
    }

    if (data.message.reply) {
      mergeThreadReplies([data.message.reply])
    } else {
      await fetchThreadMessages()
    }

    messages.value = messages.value.map((message) => {
      if (message.name !== threadParent.value?.name) {
        return message
      }

      return {
        ...message,
        thread_count: (message.thread_count || 0) + 1,
      }
    })
    await scrollThreadToBottom()
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    threadError.value = err instanceof Error ? err.message : 'Could not send thread reply.'
  } finally {
    threadSending.value = false
  }
}

function isRealtimeChannelMatch(eventChannelId?: string) {
  if (!eventChannelId || !activeChannelName.value) {
    return false
  }

  return String(eventChannelId) === String(activeChannelName.value)
}

function setupRealtimeListeners() {
  cleanupRealtimeListeners()

  if (!window.frappe?.realtime?.on) {
    realtimeReady.value = false
    realtimeStatus.value = 'Live unavailable'
    return
  }

  window.frappe.realtime.on('raven:unread_channel_count_updated', handleRavenChannelUpdate)
  window.frappe.realtime.on('thread_reply', handleRavenThreadReply)
  window.frappe.realtime.on('verto_mobile_raven_message', handleVertoMessageUpdate)
  window.frappe.realtime.on('verto_mobile_raven_thread_reply', handleVertoThreadReply)

  const socket = window.frappe.realtime.socket

  if (socket) {
    socket.on('connect', handleRealtimeConnect)
    socket.on('disconnect', handleRealtimeDisconnect)
    socket.on('connect_error', handleRealtimeError)

    if (socket.connected) {
      handleRealtimeConnect()
    } else {
      realtimeReady.value = false
      realtimeStatus.value = 'Connecting'
      window.frappe.realtime.connect()
    }
  } else {
    realtimeReady.value = true
    realtimeStatus.value = 'Live'
  }
}

function cleanupRealtimeListeners() {
  if (!window.frappe?.realtime?.off) {
    return
  }

  window.frappe.realtime.off('raven:unread_channel_count_updated', handleRavenChannelUpdate)
  window.frappe.realtime.off('thread_reply', handleRavenThreadReply)
  window.frappe.realtime.off('verto_mobile_raven_message', handleVertoMessageUpdate)
  window.frappe.realtime.off('verto_mobile_raven_thread_reply', handleVertoThreadReply)

  const socket = window.frappe.realtime.socket

  socket?.off('connect', handleRealtimeConnect)
  socket?.off('disconnect', handleRealtimeDisconnect)
  socket?.off('connect_error', handleRealtimeError)
}

function handleRealtimeConnect() {
  realtimeReady.value = true
  realtimeStatus.value = 'Live'
}

function handleRealtimeDisconnect() {
  realtimeReady.value = false
  realtimeStatus.value = 'Offline'
}

function handleRealtimeError() {
  realtimeReady.value = false
  realtimeStatus.value = 'Reconnecting'
}

function handleRavenChannelUpdate(data: any) {
  if (!data || data.sent_by === currentUser.value) {
    return
  }

  if (!isRealtimeChannelMatch(data.channel_id)) {
    return
  }

  fetchNewerMessages()
}

function handleVertoMessageUpdate(data: any) {
  if (!data || !isRealtimeChannelMatch(data.channel)) {
    return
  }

  if (data.message) {
    mergeMessages([data.message])
    scrollToBottom()
    return
  }

  fetchNewerMessages()
}

function handleRavenThreadReply(data: any) {
  if (!data) {
    return
  }

  const eventThreadId = String(
    data.channel ||
    data.channel_id ||
    data.thread_id ||
    ''
  )

  if (activeThreadId.value && eventThreadId === String(activeThreadId.value)) {
    fetchThreadMessages()
  }

  const parentMessageName = threadParent.value?.name

  if (parentMessageName) {
    messages.value = messages.value.map((message) => {
      if (message.name !== parentMessageName) {
        return message
      }

      return {
        ...message,
        thread_count: Number(data.number_of_replies || message.thread_count || 0),
      }
    })
  }
}

function handleVertoThreadReply(data: any) {
  if (!data || !activeThreadId.value) {
    return
  }

  const eventThreadId = String(data.channel || data.channel_id || '')

  if (eventThreadId !== String(activeThreadId.value)) {
    return
  }

  if (data.reply) {
    mergeThreadReplies([data.reply])
    scrollThreadToBottom()
    return
  }

  fetchThreadMessages()
}

watch(
  () => route.fullPath,
  async () => {
    if (!loading.value && route.path.startsWith('/chat')) {
      await selectRequestedRouteChannel()
    }
  }
)

watch(
  () => orderedMessages.value.length,
  () => {
    scrollToBottom()
  }
)

watch(
  () => orderedThreadReplies.value.length,
  () => {
    if (threadOpen.value) {
      scrollThreadToBottom()
    }
  }
)

onMounted(() => {
  loadChat()
})

onBeforeUnmount(() => {
  cleanupRealtimeListeners()
})
</script>