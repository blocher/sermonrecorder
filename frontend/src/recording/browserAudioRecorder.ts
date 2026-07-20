const PREFERRED_AUDIO_TYPES = [
  'audio/mp4',
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
]

function preferredMimeType(): string | undefined {
  return PREFERRED_AUDIO_TYPES.find((type) => MediaRecorder.isTypeSupported(type))
}

export function supportsAudioRecording(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    navigator.mediaDevices !== undefined &&
    typeof navigator.mediaDevices.getUserMedia === 'function' &&
    typeof MediaRecorder !== 'undefined'
  )
}

export class BrowserAudioRecorder {
  private chunks: Blob[] = []
  private mediaRecorder: MediaRecorder | undefined
  private stream: MediaStream | undefined

  get isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording'
  }

  async start(): Promise<void> {
    if (!supportsAudioRecording()) {
      throw new Error('Audio recording is not supported on this device.')
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      throw new Error('A recording is already in progress.')
    }

    this.chunks = []
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: true,
      },
    })

    const mimeType = preferredMimeType()
    this.mediaRecorder = new MediaRecorder(this.stream, {
      ...(mimeType ? { mimeType } : {}),
      audioBitsPerSecond: 128_000,
    })

    this.mediaRecorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) this.chunks.push(event.data)
    })

    this.mediaRecorder.start(1_000)
  }

  async stop(): Promise<Blob> {
    const recorder = this.mediaRecorder
    if (!recorder || recorder.state === 'inactive') {
      throw new Error('There is no active recording to stop.')
    }

    return new Promise((resolve, reject) => {
      const finish = () => {
        this.stopStream()
        const mimeType = recorder.mimeType || this.chunks[0]?.type || 'audio/webm'
        const audio = new Blob(this.chunks, { type: mimeType })
        this.mediaRecorder = undefined
        resolve(audio)
      }

      const fail = () => {
        this.stopStream()
        this.mediaRecorder = undefined
        reject(new Error('The recording could not be saved.'))
      }

      recorder.addEventListener('stop', finish, { once: true })
      recorder.addEventListener('error', fail, { once: true })
      recorder.stop()
    })
  }

  cancel(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    this.stopStream()
    this.mediaRecorder = undefined
    this.chunks = []
  }

  private stopStream(): void {
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = undefined
  }
}
