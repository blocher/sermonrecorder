# ADR 0008: Intentional service Transcript cleanup

## Status

Accepted

## Decision

- Diarization retains every timestamped speaker segment as raw Transcript source data.
- Cleanup keeps intentional service speech and uncertain speech; it drops only
  high-confidence incidental pew conversation.
- Speaker labels alone never decide retention. A preacher mislabeled as multiple
  speakers, readers, and secondary service voices stay in the cleaned Transcript.
- Long segments and drop ratios above a small share of speech time fail open.
- If cleanup would discard every segment, the raw segments are kept unchanged.
- Raw segments are stored so cleanup can be regenerated without retranscribing,
  and so the Congregant can review the unredacted diarization privately.
- Regenerating may set an optional consider window: the full audio file is kept,
  but only overlapping speech feeds the cleaned Transcript and Study artifacts.

## Consequences

Transcripts favor completeness over aggressive silence. Occasional pew chatter may
remain; losing sermon content is the failure mode we refuse. Congregants can
regenerate Ready Sermons after a destructive confirmation that existing Study
artifacts will be replaced.
