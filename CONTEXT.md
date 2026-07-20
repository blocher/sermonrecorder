# Sermon Recorder

A personal sermon journal for congregants: capture a live sermon from the pew, then work with transcript, summaries, and reflection prompts.

## Language

**Congregant**:
The person who uses the app to capture and reflect on sermons they hear in person.
_Avoid_: User (prefer Congregant in domain talk), member, listener, attendee

**Pew recording**:
Audio captured by a Congregant from their seat during a live service — not a house/AV feed.
_Avoid_: Broadcast recording, desk recording, livestream capture

**Sermon**:
A Congregant's personal journal entry for one preaching event: pew recording audio plus transcript and derived study content. In the app, only that Congregant can browse their library. They may intentionally publish a Share page (see below); Reflections never appear there. App Admin can see all Sermons for operations.
_Avoid_: Recording (as the product noun), session, capture, note — use Sermon for the owned entry

**App Admin**:
An operator of the central Django app who can see all Sermons across Congregants for support and operations.
_Avoid_: Superuser (implementation), staff (vague)

**Draft**:
A pew recording and optional metadata that exists only on the Congregant's device until they authenticate and upload. It is not a server Sermon yet; if the device is lost before upload, the Draft is lost. A new Draft recording can be started from anywhere in the app with one tap — login, Church, Preacher, and other fields are never required to begin; at most one Draft may be recording at a time (tap again stops).
_Avoid_: Local sermon, pending sermon, offline sermon (those blur Draft vs Sermon)

**Church**:
A reusable place in a Congregant's personal place book where a Sermon was heard. May originate from a location-API suggestion or from a Congregant-created one-off; once created, that Congregant can pick it again. Other Congregants do not see it. A Sermon stores a Church reference (or remains unassigned), not a throwaway free-text string. Precise location is requested after recording stops (or when enriching metadata before upload), never as a gate on Record; if permission is denied, Church is manual only.
_Avoid_: Location (the GPS fix), venue, POI, place label (as the stored entity), global church directory (not v1)

**Preacher**:
A reusable person entry in a Congregant's personal preacher book — who delivered the sermon. Created or confirmed by that Congregant; optional on a Sermon so capture is never blocked on naming. Other Congregants do not see it.
_Avoid_: Speaker (too broad — diarization speakers ≠ Preacher), pastor, priest (role labels, not the entity)

**Occasion kind**:
A value from the app's standard list classifying the service type for filtering (e.g. Sunday, feast, wedding, funeral, midweek, other). Shared vocabulary, not Congregant-invented.
_Avoid_: Occasion alone (ambiguous with Liturgical day), category, type

**Liturgical day**:
The specific named day or observance for a Sermon (e.g. "Third Sunday of Ordinary Time"), entered manually in v1. Optional; distinct from Occasion kind. May later be filled or suggested from a tradition-specific calendar/lectionary source.
_Avoid_: Occasion (alone), feast name (too narrow), lectionary entry (implementation)

**Study artifact**:
One independently editable piece of derived content on a Sermon (short summary, long summary, outline, adult discussion questions, kids discussion questions, and similar). Regenerating one artifact does not replace the others; Congregant edits to an artifact are kept until that artifact is regenerated. Key themes are not a separate artifact — they surface as suggested Tags.
_Avoid_: Generated content (as a single blob), AI output, section

**Scripture reference**:
A structured biblical citation tied to a Sermon (e.g. Luke 15:11–32), usually AI-suggested and Congregant-editable. Tappable to an external Bible app or site; included on the Share page; findable via Library search. Not a full in-app Bible reader.
_Avoid_: Bible link (UI only), reading (liturgical role, not the citation entity), pericope (too narrow/jargon)

**Tag**:
A label in the Congregant's personal tag book used to file and filter Sermons. AI may suggest Tags (including from inferred themes); the Congregant confirms, edits, or ignores. There is no separate "themes" entity.
_Avoid_: Theme (as a stored entity), category, keyword

**Reflection**:
A Congregant's personal journal response tied to a Sermon — freeform or started from a prompt. Distinct from discussion-question Study artifacts, which are material for group/family use and need not be answered in-app.
_Avoid_: Journal entry (as the only name), diary, answer (too tied to quiz-style questions)

**Transcript**:
The cleaned, timestamped text of a Sermon's pew recording meant for reading and skip-to playback. Built by identifying the predominant speaker and dropping side conversation; the Congregant edits this text, not a full multi-speaker tape.
_Avoid_: Diarization (the process), full tape, captions

**Related Sermon**:
A link from one Sermon to another Sermon in the same Congregant's library, suggested by similarity (tags, content). Never points at another Congregant's Sermon.
_Avoid_: Recommended sermon (implies global/catalog), similar sermon (vague)

**Ready**:
The Sermon state when processing is complete enough to notify the Congregant: pew recording stored, Transcript, all Study artifacts, Scripture references, Tag suggestions applied or available, and Related Sermons computed. One alert fires at Ready — not at partial milestones.
_Avoid_: Processed, complete, done (vague); staged "transcript ready" alerts (not v1)

**Library search**:
Full-text search over a Congregant's own Sermons — metadata, Study artifacts, Transcript, and Reflections — plus filters for Preacher, Church, Tag, Occasion kind, and date. Does not search other Congregants' content.
_Avoid_: Global search, catalog search, semantic search (as the v1 requirement)

**Share page**:
An unauthenticated web view of a Sermon's shareable projection: Study artifacts, Scripture references, Transcript, and audio playback, plus whatever metadata the Congregant includes — never Reflections. Reached via an unlisted, guess-resistant link the Congregant can send with native share or email; the Congregant can revoke or rotate the link. Not part of anyone else's in-app library and not an SEO catalog.
_Avoid_: Public sermon (implies catalog/SEO), shared sermon (implies multi-owner)

**Email recipient**:
A reusable address in the Congregant's personal email book for sending a beautiful sermon email (typically linking to or summarizing a Share page).
_Avoid_: Contact (vague), user (not a Congregant account)
