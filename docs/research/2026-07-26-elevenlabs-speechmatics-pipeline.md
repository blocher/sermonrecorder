# ElevenLabs Voice Isolator + Speechmatics batch transcription

Research notes for Pewcorder's isolate-then-transcribe pipeline (2026-07-26).

## Env keys

| Variable | Required | Purpose |
|----------|----------|---------|
| `ELEVENLABS_API_KEY` | Yes (when isolation enabled) | ElevenLabs API key (`xi-api-key` header) |
| `SPEECHMATICS_API_KEY` | Yes (default transcriber) | Speechmatics Bearer token |
| `OPENAI_API_KEY` | Yes | Study artifacts + intentional-service transcript cleanup (unchanged) |

Optional: `ELEVENLABS_API_BASE_URL`, `SPEECHMATICS_API_BASE_URL`, `SERMON_VOICE_ISOLATION_ENABLED`, `SERMON_TRANSCRIBER`, `SPEECHMATICS_MODEL`, `SPEECHMATICS_LANGUAGE`.

## ElevenLabs Voice Isolator

- Endpoint: `POST https://api.elevenlabs.io/v1/audio-isolation`
- Auth: `xi-api-key: <ELEVENLABS_API_KEY>`
- Body: multipart `audio` file (+ optional `file_format=other`)
- Response: binary audio stream (not JSON)
- Limits: up to 500 MB / 1 hour; billed at 1000 characters per minute of audio
- Docs: https://elevenlabs.io/docs/api-reference/audio-isolation/convert
- Capability overview: https://elevenlabs.io/docs/overview/capabilities/voice-isolator
- Pewcorder skips isolation (continues with loudnorm + Speechmatics) when a
  Sermon exceeds that 1-hour / 500 MB ceiling — otherwise processing would fail.

## Speechmatics batch

- Submit: `POST https://us1.asr.api.speechmatics.com/v2/jobs` with multipart `config` JSON + `data_file`
  (also `eu1` / `au1`; bare `asr.api.speechmatics.com` often returns 401)
- Auth: `Authorization: Bearer <SPEECHMATICS_API_KEY>`
- Env: `SPEECHMATICS_API_BASE_URL` default `https://us1.asr.api.speechmatics.com`
- Diarization config (official example):

```json
{
  "type": "transcription",
  "transcription_config": {
    "model": "enhanced",
    "language": "en",
    "diarization": "speaker",
    "speaker_diarization_config": {
      "speaker_sensitivity": 0.6,
      "prefer_current_speaker": true
    }
  }
}
```

- Word/punctuation items include `speaker` (`S1`, `S2`, … or `UU`) on alternatives
- Docs: https://docs.speechmatics.com/speech-to-text/batch/batch-diarization.md
- Auth: https://docs.speechmatics.com/get-started/authentication.md

## Pipeline order in Pewcorder

1. ElevenLabs isolate → replace stored playback (`audio_isolated_at`)
2. ffmpeg loudnorm → audible playback (`audio_normalized_at`)
3. Speechmatics enhanced + speaker diarization → raw segments
4. Existing intentional-service cleanup (OpenAI/simpleai)
5. Study artifacts (OpenAI/simpleai)
