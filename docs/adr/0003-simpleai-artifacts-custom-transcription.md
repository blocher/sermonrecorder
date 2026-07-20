# simpleai for Study artifacts; custom transcription path

Producing a cleaned Transcript from pew audio is a different job from turning that Transcript into Study artifacts, Tag suggestions, and Related Sermons. V1 uses a custom transcription integration (provider chosen for diarization and predominant-speaker cleanup) and adopts simpleai as the facade for Study artifact generation and related LLM work so those providers stay swappable. We do not force transcription through simpleai.

The first transcription adapter uses OpenAI `gpt-4o-transcribe-diarize`. Workers use ffmpeg to produce ten-minute, mono 32 kbps chunks when a recording is long or exceeds the transcription upload limit, then retain the speaker with the greatest speaking duration in each chunk. Chunk timestamps are shifted back onto the original pew recording timeline.

Study artifacts use simpleai's structured-output interface, pinned to an exact repository commit until the package has a stable release channel. Provider network logging is disabled because prompts contain private Sermon Transcripts. The processor seam still returns provider-neutral domain data, so either adapter can be replaced without changing worker lifecycle or persistence.
