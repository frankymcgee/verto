/** Monitor received audio only. This never opens or changes the crew microphone. */
export function monitorRemoteVoice(stream: MediaStream, update: (level: number) => void): () => void {
  let context: AudioContext | null = null
  let source: MediaStreamAudioSourceNode | null = null
  let analyser: AnalyserNode | null = null
  let frame = 0
  let closed = false
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioContextClass) return () => update(0)
    context = new AudioContextClass()
    source = context!.createMediaStreamSource(stream)
    analyser = context!.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    // The existing audio element plays the call. Do not connect this analyser
    // to destination, which would play the same speech twice.
    void context!.resume().catch(() => {})
    const samples = new Uint8Array(analyser.fftSize)
    let lastSpoken = 0
    let lastSample = -50
    const sample = (now: number) => {
      if (closed || !analyser) return
      if (now - lastSample < 50) { frame = requestAnimationFrame(sample); return }
      lastSample = now
      analyser.getByteTimeDomainData(samples)
      const rms = Math.sqrt(samples.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / samples.length)
      if (rms > 0.012) lastSpoken = now
      update(rms > 0.012 ? Math.min(1, rms * 9) : lastSpoken > 0 && now - lastSpoken < 160 ? 0.08 : 0)
      frame = requestAnimationFrame(sample)
    }
    frame = requestAnimationFrame(sample)
  } catch {
    update(0)
  }
  return () => {
    closed = true
    cancelAnimationFrame(frame)
    try { source?.disconnect() } catch { /* disconnected */ }
    try { analyser?.disconnect() } catch { /* disconnected */ }
    void context?.close().catch(() => {})
    update(0)
  }
}
