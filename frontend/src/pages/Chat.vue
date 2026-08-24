<!-- VERTO_CHAT_ALL_DRAWERS_SLIDE_UP_2026_06_11 -->
<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="flex h-full min-h-0 flex-col overflow-hidden">
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
        <div class="shrink-0 border-b border-outline-gray-1 bg-surface-white px-[var(--verto-page-x,0.75rem)] py-2">
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
          class="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]"
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

              <button
                v-if="hasDocumentLink(message)"
                type="button"
                class="mt-2 block w-full rounded-xl border p-3 text-left transition active:scale-[0.99]"
                :class="isOwnMessage(message)
                  ? 'border-white/20 bg-white/15 text-white'
                  : 'border-outline-gray-1 bg-surface-gray-1 text-ink-gray-9'"
                @click="openDocumentPreview(message)"
              >
                <div class="flex items-start gap-3">
                  <div
                    v-if="getDocumentPreviewImage(message)"
                    class="h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-current/10"
                  >
                    <img
                      :src="getDocumentPreviewImage(message)"
                      :alt="getDocumentPreviewTitle(message)"
                      class="h-full w-full object-cover"
                      loading="lazy"
                      @load="scrollToBottom"
                    >
                  </div>

                  <div
                    v-else
                    class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xs font-semibold"
                    :class="isOwnMessage(message)
                      ? 'bg-white/20 text-white'
                      : 'bg-surface-white text-ink-gray-7'"
                  >
                    DOC
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-1">
                      <span
                        class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        :class="isOwnMessage(message)
                          ? 'bg-white/20 text-white'
                          : 'bg-surface-white text-ink-gray-7'"
                      >
                        {{ getDocumentPreviewDoctype(message) }}
                      </span>

                      <span
                        class="truncate text-xs"
                        :class="isOwnMessage(message) ? 'text-white/75' : 'text-ink-gray-5'"
                      >
                        {{ getDocumentPreviewId(message) }}
                      </span>
                    </div>

                    <p class="mt-1 truncate text-sm font-semibold">
                      {{ getDocumentPreviewTitle(message) }}
                    </p>

                    <dl
                      v-if="getDocumentPreviewFields(message).length"
                      class="mt-2 space-y-1"
                    >
                      <div
                        v-for="field in getDocumentPreviewFields(message)"
                        :key="`${message.name}-${field.label}`"
                        class="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 text-xs"
                      >
                        <dt
                          class="truncate font-medium"
                          :class="isOwnMessage(message) ? 'text-white/75' : 'text-ink-gray-5'"
                        >
                          {{ field.label }}
                        </dt>

                        <dd class="truncate">
                          {{ field.value }}
                        </dd>
                      </div>
                    </dl>

                    <p
                      v-else
                      class="mt-1 text-xs"
                      :class="isOwnMessage(message) ? 'text-white/75' : 'text-ink-gray-5'"
                    >
                      Tap to open document
                    </p>
                  </div>
                </div>
              </button>

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

          <div
            ref="messagesBottomEl"
            class="h-px w-full shrink-0"
            aria-hidden="true"
          />
        </div>

        <form
          class="shrink-0 border-t border-outline-gray-1 bg-surface-white p-[var(--verto-page-x,0.75rem)]"
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
    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="previewAttachment"
          class="fixed inset-0 z-[70] flex items-end bg-black/60"
          @click.self="closePreview"
        >
          <Card class="drawer-panel flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
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
      </Transition>
    </Teleport>

    <!-- Thread Drawer -->
    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="threadOpen"
          class="fixed inset-0 z-[65] flex items-end bg-black/50"
          @click.self="closeThread"
        >
          <Card class="drawer-panel flex max-h-[88dvh] w-full flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
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

              <button
                v-if="hasDocumentLink(threadParent)"
                type="button"
                class="mt-2 block w-full rounded-xl border border-outline-gray-1 bg-surface-gray-1 p-3 text-left text-ink-gray-9 transition active:scale-[0.99]"
                @click="openDocumentPreview(threadParent)"
              >
                <div class="flex items-start gap-3">
                  <div
                    v-if="getDocumentPreviewImage(threadParent)"
                    class="h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-surface-gray-2"
                  >
                    <img
                      :src="getDocumentPreviewImage(threadParent)"
                      :alt="getDocumentPreviewTitle(threadParent)"
                      class="h-full w-full object-cover"
                      loading="lazy"
                    >
                  </div>

                  <div
                    v-else
                    class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-surface-white text-xs font-semibold text-ink-gray-7"
                  >
                    DOC
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-1">
                      <span class="rounded-full bg-surface-white px-2 py-0.5 text-[10px] font-semibold text-ink-gray-7">
                        {{ getDocumentPreviewDoctype(threadParent) }}
                      </span>

                      <span class="truncate text-xs text-ink-gray-5">
                        {{ getDocumentPreviewId(threadParent) }}
                      </span>
                    </div>

                    <p class="mt-1 truncate text-sm font-semibold">
                      {{ getDocumentPreviewTitle(threadParent) }}
                    </p>

                    <dl
                      v-if="getDocumentPreviewFields(threadParent).length"
                      class="mt-2 space-y-1"
                    >
                      <div
                        v-for="field in getDocumentPreviewFields(threadParent)"
                        :key="`${threadParent.name}-${field.label}`"
                        class="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 text-xs"
                      >
                        <dt class="truncate font-medium text-ink-gray-5">
                          {{ field.label }}
                        </dt>

                        <dd class="truncate">
                          {{ field.value }}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>
              </button>
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

                <button
                  v-if="hasDocumentLink(reply)"
                  type="button"
                  class="mt-2 block w-full rounded-xl border p-3 text-left transition active:scale-[0.99]"
                  :class="isOwnMessage(reply)
                    ? 'border-white/20 bg-white/15 text-white'
                    : 'border-outline-gray-1 bg-surface-gray-1 text-ink-gray-9'"
                  @click="openDocumentPreview(reply)"
                >
                  <div class="flex items-start gap-3">
                    <div
                      v-if="getDocumentPreviewImage(reply)"
                      class="h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-current/10"
                    >
                      <img
                        :src="getDocumentPreviewImage(reply)"
                        :alt="getDocumentPreviewTitle(reply)"
                        class="h-full w-full object-cover"
                        loading="lazy"
                      >
                    </div>

                    <div
                      v-else
                      class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xs font-semibold"
                      :class="isOwnMessage(reply)
                        ? 'bg-white/20 text-white'
                        : 'bg-surface-white text-ink-gray-7'"
                    >
                      DOC
                    </div>

                    <div class="min-w-0 flex-1">
                      <div class="flex flex-wrap items-center gap-1">
                        <span
                          class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                          :class="isOwnMessage(reply)
                            ? 'bg-white/20 text-white'
                            : 'bg-surface-white text-ink-gray-7'"
                        >
                          {{ getDocumentPreviewDoctype(reply) }}
                        </span>

                        <span
                          class="truncate text-xs"
                          :class="isOwnMessage(reply) ? 'text-white/75' : 'text-ink-gray-5'"
                        >
                          {{ getDocumentPreviewId(reply) }}
                        </span>
                      </div>

                      <p class="mt-1 truncate text-sm font-semibold">
                        {{ getDocumentPreviewTitle(reply) }}
                      </p>
                    </div>
                  </div>
                </button>

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
      </Transition>
    </Teleport>
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
import { openAppBrowser } from '../lib/appBrowser'

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
const messagesBottomEl = ref<HTMLElement | null>(null)
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
const threadCounts = ref<Record<string, number>>({})
const hydratingThreadCounts = ref(false)

const FALLBACK_REFRESH_INTERVAL_MS = 60_000
let fallbackRefreshTimer: number | undefined
let fallbackRefreshInFlight = false
const visibleMessageHtmlCache = new Map<string, string>()
const VISIBLE_MESSAGE_HTML_CACHE_LIMIT = 300

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
    hydrateThreadCountsForMessages()
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

function decodeHtmlDeep(value: string) {
  let current = String(value || '')

  for (let index = 0; index < 3; index += 1) {
    const decoded = decodeHtml(current)

    if (decoded === current) {
      break
    }

    current = decoded
  }

  return current
}

function containsHtml(value: string) {
  return /<([a-z][\w:-]*)(?:\s[^>]*)?>[\s\S]*?<\/\1>|<(br|hr|img|input|meta|link)(?:\s[^>]*)?\/?>/i.test(value)
}

function looksLikeEncodedHtml(value: string) {
  return /&lt;[a-z][\s\S]*?&gt;/i.test(value)
}

function looksLikeTiptapJson(value: string) {
  const trimmed = String(value || '').trim()

  return trimmed.startsWith('{') && trimmed.includes('"type"') && trimmed.includes('"doc"')
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

function isSafeUrl(value?: string) {
  const url = String(value || '').trim()

  return Boolean(
    url &&
      (
        url.startsWith('/') ||
        url.startsWith('#') ||
        /^https?:\/\//i.test(url) ||
        /^mailto:/i.test(url) ||
        /^tel:/i.test(url) ||
        /^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);base64,/i.test(url)
      )
  )
}

function wrapMarks(value: string, marks?: any[]) {
  let html = value

  for (const mark of marks || []) {
    const type = mark?.type
    const attrs = mark?.attrs || {}

    if (type === 'bold') {
      html = `<strong>${html}</strong>`
    } else if (type === 'italic') {
      html = `<em>${html}</em>`
    } else if (type === 'underline') {
      html = `<u>${html}</u>`
    } else if (type === 'strike') {
      html = `<s>${html}</s>`
    } else if (type === 'code') {
      html = `<code>${html}</code>`
    } else if (type === 'link' && isSafeUrl(attrs.href)) {
      html = `<a href="${escapeHtml(attrs.href)}">${html}</a>`
    }
  }

  return html
}

function renderTiptapNode(node: any): string {
  if (!node || typeof node !== 'object') {
    return ''
  }

  const type = node.type
  const attrs = node.attrs || {}
  const content = Array.isArray(node.content)
    ? node.content.map((child: any) => renderTiptapNode(child)).join('')
    : ''

  if (type === 'doc') {
    return content
  }

  if (type === 'text') {
    return wrapMarks(escapeHtml(String(node.text || '')), node.marks)
  }

  if (type === 'paragraph') {
    return `<p>${content}</p>`
  }

  if (type === 'hardBreak') {
    return '<br>'
  }

  if (type === 'bulletList') {
    return `<ul>${content}</ul>`
  }

  if (type === 'orderedList') {
    return `<ol>${content}</ol>`
  }

  if (type === 'listItem') {
    return `<li>${content}</li>`
  }

  if (type === 'blockquote') {
    return `<blockquote>${content}</blockquote>`
  }

  if (type === 'codeBlock') {
    return `<pre><code>${escapeHtml(node.text || content)}</code></pre>`
  }

  if (type === 'heading') {
    const level = Math.min(6, Math.max(1, Number(attrs.level || 2)))
    return `<h${level}>${content}</h${level}>`
  }

  if (type === 'image' && isSafeUrl(attrs.src)) {
    return `<img src="${escapeHtml(attrs.src)}" alt="${escapeHtml(attrs.alt || '')}">`
  }

  if (type === 'table') {
    return `<table>${content}</table>`
  }

  if (type === 'tableRow') {
    return `<tr>${content}</tr>`
  }

  if (type === 'tableHeader') {
    return `<th>${content}</th>`
  }

  if (type === 'tableCell') {
    return `<td>${content}</td>`
  }

  return content
}

function tiptapJsonToHtml(value: string) {
  try {
    const parsed = JSON.parse(value)

    if (!parsed || parsed.type !== 'doc') {
      return ''
    }

    return renderTiptapNode(parsed)
  } catch {
    return ''
  }
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
    'H1',
    'H2',
    'H3',
    'H4',
    'H5',
    'H6',
    'HR',
    'I',
    'IMG',
    'LI',
    'OL',
    'P',
    'PRE',
    'S',
    'SPAN',
    'STRONG',
    'TABLE',
    'TBODY',
    'TD',
    'TH',
    'THEAD',
    'TR',
    'U',
    'UL',
  ])

  const allowedAttributes: Record<string, Set<string>> = {
    A: new Set(['href', 'target', 'rel', 'title']),
    IMG: new Set(['src', 'alt', 'title', 'width', 'height', 'loading']),
    TD: new Set(['colspan', 'rowspan']),
    TH: new Set(['colspan', 'rowspan']),
  }

  function cleanElement(element: HTMLElement) {
    const tagName = element.tagName.toUpperCase()

    for (const attribute of Array.from(element.attributes)) {
      const attrName = attribute.name.toLowerCase()
      const allowedForTag = allowedAttributes[tagName]
      const isAllowed = allowedForTag?.has(attrName) || false

      if (!isAllowed) {
        element.removeAttribute(attribute.name)
        continue
      }

      if ((tagName === 'A' && attrName === 'href') || (tagName === 'IMG' && attrName === 'src')) {
        if (!isSafeUrl(attribute.value)) {
          element.removeAttribute(attribute.name)
        }
      }
    }

    if (tagName === 'A') {
      element.setAttribute('target', '_blank')
      element.setAttribute('rel', 'noopener noreferrer')
    }

    if (tagName === 'IMG') {
      element.setAttribute('loading', 'lazy')
    }
  }

  function cleanNode(node: Node) {
    const children = Array.from(node.childNodes)

    for (const child of children) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const element = child as HTMLElement
        const tagName = element.tagName.toUpperCase()

        if (!allowedTags.has(tagName)) {
          const replacementChildren = Array.from(element.childNodes)
          element.replaceWith(...replacementChildren)

          for (const replacementChild of replacementChildren) {
            cleanNode(replacementChild)
          }

          continue
        }

        cleanElement(element)
        cleanNode(element)
      } else if (child.nodeType === Node.COMMENT_NODE) {
        child.remove()
      }
    }
  }

  cleanNode(template.content)

  return template.innerHTML.trim()
}

function getMessageBodyCandidates(message: RavenMessage) {
  const rawMessage = message as any

  return [
    rawMessage.html,
    rawMessage.html_message,
    rawMessage.message_html,
    rawMessage.content_html,
    rawMessage.text_html,
    rawMessage.formatted_text,
    rawMessage.formatted_message,
    rawMessage.rich_text,
    rawMessage.rich_text_content,
    rawMessage.message,
    rawMessage.content,
    rawMessage.text,
  ].filter((value) => value !== undefined && value !== null)
}

function getRawDisplayText(message: RavenMessage) {
  const candidates = getMessageBodyCandidates(message)

  for (const candidate of candidates) {
    const value = String(candidate || '').trim()

    if (!value) {
      continue
    }

    const decoded = decodeHtmlDeep(value)

    if (containsHtml(decoded) || looksLikeEncodedHtml(value)) {
      return decoded
    }
  }

  for (const candidate of candidates) {
    const value = String(candidate || '').trim()
    const decoded = decodeHtmlDeep(value)

    if (looksLikeTiptapJson(decoded)) {
      const html = tiptapJsonToHtml(decoded)

      if (html) {
        return html
      }
    }
  }

  for (const candidate of candidates) {
    const value = String(candidate || '').trim()

    if (value) {
      return value
    }
  }

  return ''
}

type DocumentPreviewField = {
  label: string
  value: string
}

function getMessageDocumentPreview(message?: RavenMessage | null) {
  return ((message as any)?.document_preview || null) as Record<string, any> | null
}

function getDocumentPreviewDoctype(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)

  return String(
    (message as any)?.link_doctype ||
      (message as any)?.linked_doctype ||
      (message as any)?.reference_doctype ||
      (message as any)?.document_type ||
      preview?.doctype ||
      ''
  ).trim()
}

function getDocumentPreviewDocname(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)

  return String(
    (message as any)?.link_document ||
      (message as any)?.linked_docname ||
      (message as any)?.reference_docname ||
      (message as any)?.document_name ||
      preview?.docname ||
      preview?.id ||
      ''
  ).trim()
}

function hasDocumentLink(message?: RavenMessage | null) {
  if (!message) {
    return false
  }

  return Boolean(getDocumentPreviewDoctype(message) && getDocumentPreviewDocname(message))
}

function getDocumentPreviewTitle(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)
  const raw = preview?.raw || {}

  return String(
    preview?.title ||
      preview?.preview_title ||
      raw.preview_title ||
      getDocumentPreviewDocname(message)
  ).trim()
}

function getDocumentPreviewId(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)

  return String(
    preview?.id ||
      preview?.docname ||
      getDocumentPreviewDocname(message)
  ).trim()
}

function getDocumentPreviewImage(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)
  const raw = preview?.raw || {}

  return String(
    preview?.preview_image ||
      raw.preview_image ||
      ''
  ).trim()
}

function getDocumentPreviewRoute(message?: RavenMessage | null) {
  const preview = getMessageDocumentPreview(message)
  const raw = preview?.raw || {}
  const route = String(preview?.route || raw.raven_document_link || '').trim()

  if (route) {
    return route
  }

  const doctype = getDocumentPreviewDoctype(message)
  const docname = getDocumentPreviewDocname(message)
  const slug = doctype
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')

  return `/app/${encodeURIComponent(slug)}/${encodeURIComponent(docname)}`
}

function getDocumentPreviewFields(message?: RavenMessage | null): DocumentPreviewField[] {
  const preview = getMessageDocumentPreview(message)
  const fields = Array.isArray(preview?.fields) ? preview.fields : []

  if (fields.length) {
    return fields
      .filter((field: Record<string, any>) => field?.label && field?.value !== undefined && field?.value !== null && String(field.value).trim() !== '')
      .slice(0, 6)
      .map((field: Record<string, any>) => ({
        label: String(field.label),
        value: String(field.value),
      }))
  }

  const raw = preview?.raw || {}
  const hiddenFields = new Set([
    'preview_image',
    'preview_title',
    'id',
    'raven_document_link',
  ])

  return Object.keys(raw)
    .filter((key) => !hiddenFields.has(key) && raw[key] !== undefined && raw[key] !== null && String(raw[key]).trim() !== '')
    .slice(0, 6)
    .map((key) => ({
      label: key,
      value: String(raw[key]),
    }))
}

function openDocumentPreview(message?: RavenMessage | null) {
  if (!hasDocumentLink(message)) {
    return
  }

  openAppBrowser({
    url: getDocumentPreviewRoute(message),
    title: getDocumentPreviewTitle(message) || getDocumentPreviewDocname(message),
  })
}

function getVisibleMessageHtml(message: RavenMessage) {
  const raw = getRawDisplayText(message).trim()

  if (!raw) return ''

  const cached = visibleMessageHtmlCache.get(raw)

  if (cached !== undefined) {
    return cached
  }

  const decoded = decodeHtmlDeep(raw)
  const tiptapHtml = looksLikeTiptapJson(decoded) ? tiptapJsonToHtml(decoded) : ''
  const html = tiptapHtml
    ? sanitiseMessageHtml(tiptapHtml)
    : containsHtml(decoded)
      ? sanitiseMessageHtml(decoded)
      : textToHtml(raw)

  if (visibleMessageHtmlCache.size >= VISIBLE_MESSAGE_HTML_CACHE_LIMIT) {
    visibleMessageHtmlCache.clear()
  }

  visibleMessageHtmlCache.set(raw, html)

  return html
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

function getNumericThreadCountValue(value: unknown) {
  const count = Number(value)

  if (!Number.isFinite(count)) {
    return 0
  }

  return Math.max(0, Math.round(count))
}

function getThreadCount(message: RavenMessage) {
  const directCount = getNumericThreadCountValue(
    message.number_of_replies ??
      message.thread_count ??
      message.reply_count ??
      message.replies_count ??
      message.thread_replies_count ??
      message.total_replies ??
      message.reply_count_on_thread ??
      message.thread_reply_count
  )

  if (directCount > 0) {
    return directCount
  }

  return threadCounts.value[message.name] || 0
}

function shouldShowThreadButton(message: RavenMessage) {
  return Boolean(message.is_thread) || getThreadCount(message) > 0
}

function getThreadButtonLabel(message: RavenMessage) {
  const count = getThreadCount(message)
  return count ? `Open thread · ${count}` : 'Open thread'
}

async function hydrateThreadCountsForMessages() {
  if (hydratingThreadCounts.value) {
    return
  }

  const missingThreadCounts = chat.messages.value.filter((message) => {
    return Boolean(message.is_thread) && !getThreadCount(message) && !threadCounts.value[message.name]
  })

  if (!missingThreadCounts.length) {
    return
  }

  hydratingThreadCounts.value = true

  try {
    const nextCounts = { ...threadCounts.value }

    await Promise.all(
      missingThreadCounts.slice(0, 12).map(async (message) => {
        try {
          const threadData = await getMessages(message.name, 100)
          nextCounts[message.name] = threadData.messages.length
        } catch {
          nextCounts[message.name] = 0
        }
      })
    )

    threadCounts.value = nextCounts
  } finally {
    hydratingThreadCounts.value = false
  }
}

function setKnownThreadCount(messageName: string, count: number) {
  if (!messageName) {
    return
  }

  threadCounts.value = {
    ...threadCounts.value,
    [messageName]: Math.max(0, Math.round(count)),
  }
}

function scrollElementToBottom(element: HTMLElement | null) {
  if (!element) return

  element.scrollTop = element.scrollHeight
}

function isNearBottom(element: HTMLElement | null, threshold = 120) {
  if (!element) return true

  return element.scrollTop + element.clientHeight >= element.scrollHeight - threshold
}

function runScrollToBottom(element: HTMLElement | null, marker?: HTMLElement | null) {
  scrollElementToBottom(element)

  if (marker) {
    marker.scrollIntoView({
      block: 'end',
      inline: 'nearest',
      behavior: 'auto',
    })
  }
}

async function scrollToBottom() {
  await nextTick()

  const run = () => runScrollToBottom(messagesEl.value, messagesBottomEl.value)

  run()

  requestAnimationFrame(() => {
    run()

    requestAnimationFrame(() => {
      run()
    })
  })

  window.setTimeout(run, 80)
  window.setTimeout(run, 250)
  window.setTimeout(run, 600)
}

async function scrollThreadToBottom() {
  await nextTick()

  const run = () => scrollElementToBottom(threadMessagesEl.value)

  run()

  requestAnimationFrame(() => {
    run()

    requestAnimationFrame(() => {
      run()
    })
  })

  window.setTimeout(run, 80)
  window.setTimeout(run, 250)
  window.setTimeout(run, 600)
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

  if (threadParent.value?.name) {
    setKnownThreadCount(threadParent.value.name, threadReplies.value.length)
  }
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
    const data = await getMessages(activeThreadId.value, 100)
    threadReplies.value = data.messages

    if (threadParent.value?.name) {
      setKnownThreadCount(threadParent.value.name, data.messages.length)
    }

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
      setKnownThreadCount(message.name, threadReplies.value.length)
    }

    if (!threadId) {
      const createdOrLoaded = await getMessageThread(message.name)
      threadId = createdOrLoaded.thread_id || ''
      threadParent.value = createdOrLoaded.parent || message
      threadReplies.value = sortMessagesOldestFirst(createdOrLoaded.replies || [])
      setKnownThreadCount(message.name, threadReplies.value.length)
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

async function fallbackRefreshFromRaven() {
  if (fallbackRefreshInFlight || chat.loading.value || !chat.activeChannelId.value) {
    return
  }

  fallbackRefreshInFlight = true

  const beforeLatestMessage = getLatestMessageName(chat.messages.value)
  const beforeThreadLatestMessage = getLatestMessageName(threadReplies.value)
  const shouldStayAtBottom = isNearBottom(messagesEl.value, 180)

  try {
    await chat.fetchNewer()
    await hydrateThreadCountsForMessages()

    const afterLatestMessage = getLatestMessageName(chat.messages.value)

    if (afterLatestMessage && (afterLatestMessage !== beforeLatestMessage || shouldStayAtBottom)) {
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
    console.warn('[verto raven fallback] refresh failed', err)
  } finally {
    fallbackRefreshInFlight = false
  }
}

function startFallbackRefreshPolling() {
  stopFallbackRefreshPolling()

  fallbackRefreshTimer = window.setInterval(() => {
    if (
      document.visibilityState === 'visible'
      && navigator.onLine
    ) {
      if (!realtime.isConnected()) {
        realtime.ensureConnected()
      }

      void fallbackRefreshFromRaven()
    }
  }, FALLBACK_REFRESH_INTERVAL_MS)
}

async function recoverLiveChat() {
  if (
    document.visibilityState !== 'visible'
    || !navigator.onLine
    || chat.loading.value
    || !chat.activeChannelId.value
  ) {
    return
  }

  const healthy = await realtime.ensureHealthy()

  if (healthy) {
    realtime.resubscribeAll()
  }

  await fallbackRefreshFromRaven()
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible') {
    void recoverLiveChat()
  }
}

function stopFallbackRefreshPolling() {
  if (fallbackRefreshTimer) {
    window.clearInterval(fallbackRefreshTimer)
    fallbackRefreshTimer = undefined
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
  await hydrateThreadCountsForMessages()
  realtime.resubscribeAll()
  startFallbackRefreshPolling()
  await scrollToBottom()
}

watch(
  () => route.fullPath,
  async () => {
    await chat.load()
    await hydrateThreadCountsForMessages()
    realtime.resubscribeAll()
    startFallbackRefreshPolling()
    await handlePeriAutoSend()
    await scrollToBottom()
  }
)

onMounted(async () => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('pageshow', recoverLiveChat)
  window.addEventListener('online', recoverLiveChat)

  await loadMobileBoot()
  await chat.load()
  await hydrateThreadCountsForMessages()
  realtime.start()
  startFallbackRefreshPolling()
  await handlePeriAutoSend()
  await scrollToBottom()
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('pageshow', recoverLiveChat)
  window.removeEventListener('online', recoverLiveChat)
  stopFallbackRefreshPolling()
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

.rich-message-html :deep(h1),
.rich-message-html :deep(h2),
.rich-message-html :deep(h3),
.rich-message-html :deep(h4),
.rich-message-html :deep(h5),
.rich-message-html :deep(h6) {
  margin: 0.45rem 0 0.25rem;
  font-weight: 700;
  line-height: 1.25;
}

.rich-message-html :deep(h1) {
  font-size: 1.15rem;
}

.rich-message-html :deep(h2),
.rich-message-html :deep(h3) {
  font-size: 1.05rem;
}

.rich-message-html :deep(blockquote) {
  margin: 0.35rem 0;
  border-left: 3px solid rgba(0, 0, 0, 0.18);
  padding-left: 0.65rem;
}

.rich-message-html :deep(table) {
  margin: 0.35rem 0;
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.rich-message-html :deep(th),
.rich-message-html :deep(td) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 0.25rem 0.35rem;
  vertical-align: top;
}

.rich-message-html :deep(img) {
  max-width: 100%;
  border-radius: 0.5rem;
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


.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.18s ease;
}

.drawer-fade-slide-enter-active :deep(.drawer-panel),
.drawer-fade-slide-leave-active :deep(.drawer-panel) {
  transition: transform 0.24s ease, opacity 0.24s ease;
}

.drawer-fade-slide-enter-from,
.drawer-fade-slide-leave-to {
  opacity: 0;
}

.drawer-fade-slide-enter-from :deep(.drawer-panel),
.drawer-fade-slide-leave-to :deep(.drawer-panel) {
  opacity: 0;
  transform: translateY(100%);
}

.drawer-fade-slide-enter-to :deep(.drawer-panel),
.drawer-fade-slide-leave-from :deep(.drawer-panel) {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .drawer-fade-slide-enter-active,
  .drawer-fade-slide-leave-active,
  .drawer-fade-slide-enter-active :deep(.drawer-panel),
  .drawer-fade-slide-leave-active :deep(.drawer-panel) {
    transition: none;
  }
}


</style>
