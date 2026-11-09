import { computed, ref } from 'vue'
import { LocalAudioTrack, Room, RoomEvent, Track, type RemoteTrack } from 'livekit-client'
import { apiRequest } from '../lib/api'

type Floor = { identity: string; display_name: string } | null
type Session = {
  session_id: string; identity: string; url: string; token: string
  heartbeat_seconds: number; lease_seconds: number; max_transmission_seconds: number
}
type FloorResult = { granted: boolean; floor: Floor }
const endpoint = '/api/method/verto.api.mobile.walkie_talkie.'

async function post<T>(method: string, values: Record<string, string>, keepalive = false) {
  const result = await apiRequest<{ message: T }>(endpoint + method, {
    method: 'POST', cache: 'no-store', keepalive,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
    signal: AbortSignal.timeout(8000),
  })
  return result.message
}

export function useWalkieTalkie() {
  const connected = ref(false)
  const joining = ref(false)
  const talking = ref(false)
  const claiming = ref(false)
  const floor = ref<Floor>(null)
  const error = ref('')
  const audioBlocked = ref(false)
  const participants = ref<string[]>([])
  const status = computed(() => talking.value ? 'Transmitting' : floor.value
    ? `${floor.value.display_name} is talking` : connected.value ? 'Listening' : 'Disconnected')

  let session: Session | null = null
  let room: Room | null = null
  let track: LocalAudioTrack | null = null
  let held = false
  let generation = 0
  let heartbeatTimer: ReturnType<typeof setTimeout> | undefined
  let safetyTimer: ReturnType<typeof setTimeout> | undefined
  let maximumTimer: ReturnType<typeof setTimeout> | undefined
  let operations: Promise<void> = Promise.resolve()
  const audioElements = new Set<HTMLMediaElement>()

  function muteNow() {
    held = false
    talking.value = false
    clearTimeout(maximumTimer)
    if (track) {
      // Stop capture synchronously, before awaiting any SDK or network operation.
      track.mediaStreamTrack.enabled = false
      track.stop()
    }
  }

  function enqueue(operation: () => Promise<void>) {
    operations = operations.then(operation).catch(() => {
      muteNow()
      error.value = 'The radio connection was interrupted. Disconnect and join again.'
    })
    return operations
  }

  async function releaseTrack(activeRoom: Room | null) {
    const previous = track
    track = null
    if (previous && activeRoom) await activeRoom.localParticipant.unpublishTrack(previous, false)
  }

  function release() {
    if (!held && !track && !claiming.value) return Promise.resolve()
    muteNow()
    const active = session
    const activeRoom = room
    return enqueue(async () => {
      await releaseTrack(activeRoom)
      if (active) {
        const state = await post<FloorResult>('floor_action', { session_id: active.session_id, action: 'release' })
        if (session === active) floor.value = state.floor
      }
    })
  }

  function renewSafety(active: Session) {
    clearTimeout(safetyTimer)
    safetyTimer = setTimeout(() => {
      if (session !== active) return
      error.value = 'Connection lost. Join the channel again.'
      void disconnect()
    }, (active.lease_seconds - 2) * 1000)
  }

  async function heartbeat(active: Session) {
    try {
      const state = await post<FloorResult>('floor_action', { session_id: active.session_id, action: 'heartbeat' })
      if (session !== active) return
      floor.value = state.floor
      if (talking.value && !state.granted) {
        void release()
        error.value = 'Transmission ended. Release the button before talking again.'
      }
      renewSafety(active)
      heartbeatTimer = setTimeout(() => void heartbeat(active), active.heartbeat_seconds * 1000)
    } catch {
      if (session !== active) return
      error.value = 'Connection lost or channel access changed. Join the channel again.'
      void disconnect()
    }
  }

  async function disconnect() {
    generation++
    muteNow()
    clearTimeout(heartbeatTimer)
    clearTimeout(safetyTimer)
    const previousSession = session
    const previousRoom = room
    session = null
    room = null
    connected.value = false
    joining.value = false
    claiming.value = false
    floor.value = null
    participants.value = []
    audioBlocked.value = false
    for (const element of audioElements) element.remove()
    audioElements.clear()
    // Do not wait for the control API before closing the audio transport.
    if (previousRoom) void previousRoom.disconnect().catch(() => {})
    await enqueue(async () => {
      await releaseTrack(previousRoom)
      if (previousSession) {
        await post('leave_channel', { session_id: previousSession.session_id }, true).catch(() => {})
      }
    })
  }

  async function join(channel: string) {
    if (joining.value || connected.value) return
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      error.value = 'Walkie talkie needs HTTPS and a browser with microphone support.'
      return
    }
    const attempt = ++generation
    joining.value = true
    error.value = ''
    try {
      await operations
      if (attempt !== generation) return
      const active = await post<Session>('join_channel', { channel })
      if (attempt !== generation) {
        void post('leave_channel', { session_id: active.session_id }, true).catch(() => {})
        return
      }
      session = active
      const activeRoom = new Room({ adaptiveStream: true, dynacast: true })
      room = activeRoom
      const updateParticipants = () => {
        if (room !== activeRoom) return
        participants.value = [activeRoom.localParticipant, ...activeRoom.remoteParticipants.values()]
          .map(participant => participant.name || 'Team member')
      }
      activeRoom.on(RoomEvent.TrackSubscribed, (remote: RemoteTrack) => {
        if (remote.kind !== Track.Kind.Audio || room !== activeRoom) return
        const element = remote.attach()
        element.autoplay = true
        element.setAttribute('playsinline', '')
        document.body.appendChild(element)
        audioElements.add(element)
      })
      activeRoom.on(RoomEvent.TrackUnsubscribed, (remote: RemoteTrack) => {
        for (const element of remote.detach()) { audioElements.delete(element); element.remove() }
      })
      activeRoom.on(RoomEvent.ParticipantConnected, updateParticipants)
      activeRoom.on(RoomEvent.ParticipantDisconnected, updateParticipants)
      activeRoom.on(RoomEvent.AudioPlaybackStatusChanged, () => {
        if (room === activeRoom) audioBlocked.value = !activeRoom.canPlaybackAudio
      })
      activeRoom.on(RoomEvent.Reconnecting, () => {
        if (room !== activeRoom) return
        error.value = 'Audio connection interrupted. Join the channel again.'
        void disconnect()
      })
      activeRoom.on(RoomEvent.Disconnected, () => {
        if (room === activeRoom) void disconnect()
      })
      await activeRoom.connect(active.url, active.token, { autoSubscribe: true })
      if (attempt !== generation) { await activeRoom.disconnect(); return }
      await activeRoom.startAudio().catch(() => { audioBlocked.value = true })
      if (attempt !== generation) return
      connected.value = true
      updateParticipants()
      renewSafety(active)
      void heartbeat(active)
    } catch (cause) {
      if (attempt !== generation) return
      error.value = cause instanceof Error ? cause.message : 'Could not join the channel.'
      await disconnect()
    } finally {
      if (attempt === generation) joining.value = false
    }
  }

  function hold() {
    if (!connected.value || claiming.value || held || !session || !room) return
    held = true
    claiming.value = true
    error.value = ''
    const active = session
    const activeRoom = room
    const stillHeld = () => held && session === active && connected.value
    return enqueue(async () => {
      try {
        if (!stillHeld()) return
        const result = await post<FloorResult>('floor_action', { session_id: active.session_id, action: 'claim' })
        if (session === active) floor.value = result.floor
        if (!result.granted) { held = false; return }
        // The server permission update may arrive after its HTTP response.
        const until = Date.now() + 3000
        while (stillHeld() && !activeRoom.localParticipant.permissions?.canPublish && Date.now() < until) {
          await new Promise(resolve => setTimeout(resolve, 25))
        }
        if (!stillHeld()) return
        if (!activeRoom.localParticipant.permissions?.canPublish) throw new Error('Could not start transmission. Try again.')
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false,
        })
        const microphone = stream.getAudioTracks()[0]
        for (const source of stream.getTracks()) source.enabled = false
        if (!stillHeld()) { stream.getTracks().forEach(source => source.stop()); return }
        track = new LocalAudioTrack(microphone, undefined, true)
        await track.mute()
        await activeRoom.localParticipant.publishTrack(track, { source: Track.Source.Microphone })
        if (!stillHeld()) return
        await track.unmute()
        if (!stillHeld()) { muteNow(); return }
        talking.value = true
        maximumTimer = setTimeout(() => {
          error.value = 'Transmission limit reached. Release and press again to continue.'
          void release()
        }, active.max_transmission_seconds * 1000)
      } catch (cause) {
        if (session === active) error.value = cause instanceof Error ? cause.message : 'Microphone access failed.'
        muteNow()
      } finally {
        if (!stillHeld() || !talking.value) {
          muteNow()
          await releaseTrack(activeRoom)
          await post('floor_action', { session_id: active.session_id, action: 'release' }).catch(() => {})
        }
        claiming.value = false
      }
    })
  }

  async function startAudio() {
    try { await room?.startAudio(); audioBlocked.value = false }
    catch { audioBlocked.value = true }
  }

  return { connected, joining, talking, claiming, floor, error, audioBlocked, participants, status,
    join, disconnect, hold, release, startAudio }
}
