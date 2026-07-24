# ADR 0008: Intentional service Transcript cleanup

## Status

Accepted

## Decision

- Diarization retains every timestamped speaker segment as raw Transcript source data.
- Cleanup keeps intentional service speech and uncertain speech; it drops only
  high-confidence incidental pew conversation.
- Speaker labels alone never decide retention. A preacher mislabeled as multiple
  speakers, readers, and secondary service voices stay in the cleaned Transcript.
- If cleanup would discard every segment, the raw segments are kept unchanged.
- Raw segments are stored so cleanup can be regenerated without retranscribing.

## Consequences

Transcripts favor completeness over aggressive silence. Occasional pew chatter may
remain; losing sermon content is the failure mode we refuse. Congregants can
regenerate Ready Sermons after a destructive confirmation that existing Study
artifacts will be replaced.
