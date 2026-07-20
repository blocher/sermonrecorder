# simpleai for Study artifacts; custom transcription path

Producing a cleaned Transcript from pew audio is a different job from turning that Transcript into Study artifacts, Tag suggestions, and Related Sermons. V1 uses a custom transcription integration (provider chosen for diarization and predominant-speaker cleanup) and adopts simpleai as the facade for Study artifact generation and related LLM work so those providers stay swappable. We do not force transcription through simpleai.
