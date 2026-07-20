# Pewcorder design system

Pewcorder is an AI sermon journal used first in a distracted sanctuary and later in a quiet reading moment. Its interface borrows the structure of an illuminated missal without imitating historical ornament.

## Brand

- Product name: **Pewcorder**
- Descriptor: **AI Sermon Journal**
- Full store name: **Pewcorder: AI Sermon Journal**
- Use “Pewcorder” alone in compact app chrome.

The wordmark uses Fraunces; the descriptor uses Source Sans 3 in small capitals. Interface copy stays plain and does not repeat pew or recording puns.

## Palette

- `vellum` `#F1EEE4`: page ground
- `ink` `#1C2430`: primary text
- `rubric` `#9E1B2E`: recording state and rubric labels
- `lapis` `#2F4B7C`: links, Scripture, and focus
- `rule-gold` `#B8963E`: fine illuminated rules and the record seal
- `margin` `#E4E0D4`: secondary surfaces and inset wells

The interface is light-first. Gold is never a glow or primary button color. Rubric red is reserved for recording, careful/destructive actions, and compact document labels.

## Type

- **Fraunces**: wordmark, sermon titles, and restrained display headings
- **Literata**: transcripts, summaries, questions, and reflections
- **Source Sans 3**: navigation, controls, metadata, and timestamps

Transcript text is never smaller than 17px. Reading columns stay near 40rem.

## Layout

The primary frame behaves like a missal:

- one readable column with generous margins;
- rubric labels instead of decorative eyebrows;
- fine rules instead of stacks of bordered cards;
- sequence numbers only when content has a real order;
- touch targets at least 44px.

## Signature

The historiated Record seal is the one expressive object. It is circular with a gold rim, quiet on vellum while idle, and filled with rubric red while recording. Its pulse stops when reduced motion is requested.

Avoid competing medieval decoration: no ornamental crosses in app chrome, faux parchment texture, forests of drop caps, manicules, or ambient “holy” particles.

## Motion

- Record seal breathes while recording.
- Ready sermon sections enter once as a restrained gathering.
- Share pages use one soft ink fade.

All motion respects `prefers-reduced-motion`.

## Voice

Use active, direct language: “Start recording,” “Stop recording,” “Publish Share page,” and “Revoke link.” Errors state what failed and how to recover. Empty states invite action without apologizing.
