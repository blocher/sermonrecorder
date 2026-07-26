# Transcription + diarization accuracy: is OpenAI the best option?

**Date:** 2026-07-24  
**Scope:** Research only — no application code changes.  
**Question:** For speech-to-text with speaker diarization, is OpenAI’s stack (especially `gpt-4o-transcribe-diarize`) the best / most accurate option available today?

**Executive answer:** **No public primary evidence supports claiming OpenAI as the most accurate combined transcription + diarization system today.** OpenAI documents a native diarizing ASR model and reports WER gains for `gpt-4o-transcribe` over Whisper on multilingual ASR benchmarks, but it does **not** publish DER, cpWER, or other joint speaker-attribution scores for `gpt-4o-transcribe-diarize`, and that model is **absent** from the most complete vendor-comparative cpWER tables currently published. Competing vendors (notably AssemblyAI Universal-3.5 Pro and Azure Speech) publish stronger *comparative* claims on joint transcript+speaker metrics; ElevenLabs and Deepgram publish strong *ASR-only* or *self-vs-prior* claims. For sermon-length English audio, the accuracy-first next step is an **on-domain bake-off**, not a ranking inferred from marketing charts.

---

## Current SermonRecorder usage

SermonRecorder / Pewcorder defaults to OpenAI Audio Transcriptions with `OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe-diarize`, chunking long/large audio with ffmpeg and retaining the predominant speaker per chunk (see `backend/config/settings.py` and ADR 0003).

---

## How to read the evidence

| Metric | What it measures | Notes |
| --- | --- | --- |
| **WER** | Transcription errors (subs/dels/ins) vs reference text | Does **not** score speaker labels |
| **DER** | Diarization Error Rate (missed speech + false alarm + speaker confusion) / speech time | Time-based; does not require correct words |
| **cpWER** | Concatenated minimum-permutation WER | Joint score: wrong speaker on a word counts as an error; WER is a lower bound ([AssemblyAI explanation](https://www.assemblyai.com/blog/speaker-diarization-improvements)) |
| **CER (Deepgram)** | Confusion Error Rate — share of speech time attributed to the wrong speaker | Deepgram’s internal diarization metric ([Batch Diarization V2](https://deepgram.com/learn/introducing-batch-diarization-v2)) |

**Critical gap:** There is **no** published independent or vendor head-to-head that includes OpenAI `gpt-4o-transcribe-diarize` on DER or cpWER alongside AssemblyAI / Deepgram / Azure / ElevenLabs / Google / Speechmatics. Rankings below that omit OpenAI diarize **cannot** be used to declare OpenAI best or worst on joint accuracy.

Vendor-run leaderboards (including AssemblyAI’s [benchmarks page](https://www.assemblyai.com/benchmarks)) are primary *for that vendor’s claims* but are not neutral third-party science. Treat them as directional, methodology-dependent evidence.

---

## Comparison by vendor / approach

### OpenAI

| Item | Detail | Source |
| --- | --- | --- |
| Models | `whisper-1` (open Whisper V2), `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe-diarize` | [Speech to text guide](https://developers.openai.com/api/docs/guides/speech-to-text) |
| Combined ASR+diarization | **Native** on `gpt-4o-transcribe-diarize` via `response_format=diarized_json`; optional up to 4 known speaker name/reference clips (2–10 s) | [Speech to text — Speaker diarization](https://developers.openai.com/api/docs/guides/speech-to-text); [model page](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize) |
| ASR accuracy claims | `gpt-4o-transcribe` / mini: improved WER vs Whisper on FLEURS / Common Voice; better accents/noise | [Introducing next-generation audio models](https://openai.com/index/introducing-our-next-generation-audio-models/) (Mar 2025 era launch post) |
| Diarization accuracy claims | **None published** (no DER / cpWER / public joint benchmark for `-diarize`) | Model page + speech-to-text docs above |
| Practical limits | Uploads **≤ 25 MB**; for `-diarize`, `chunking_strategy` **required** when audio **> 30 s**; **no** `prompt`, logprobs, or `timestamp_granularities[]` on `-diarize` | [Speech to text](https://developers.openai.com/api/docs/guides/speech-to-text) |
| Duration note | Community-reported **1500 s (25 min)** max for `gpt-4o-transcribe` (API error text); not spelled out on the diarize model card — treat as a production risk for long sermons unless chunking | [OpenAI Developer Community](https://community.openai.com/t/gpt4-0-transcribe-max-1500-seconds/1306684) (secondary vs docs; useful operational signal) |
| Pricing (secondary) | Diarize model card lists audio tokens **$2.50 / $10.00 per 1M** input/output | [gpt-4o-transcribe-diarize](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize) |

**Product-relevant accuracy friction:** Prompting (useful for scripture names / religious vocabulary) is **explicitly unavailable** on `gpt-4o-transcribe-diarize`, while it is available on `gpt-4o-transcribe` ([docs](https://developers.openai.com/api/docs/guides/speech-to-text)).

---

### AssemblyAI (Universal-3 / Universal-3.5)

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** via `speaker_labels=true` on pre-recorded transcription; utterances with speaker labels; optional speaker count constraints | [Speaker Diarization docs](https://www.assemblyai.com/docs/pre-recorded-audio/speaker-diarization) |
| Flagship | Universal-3.5 Pro (default in their 2026 materials); Universal-3 Pro remains as a snapshot | [How accurate is speech-to-text in 2026?](https://www.assemblyai.com/blog/how-accurate-speech-to-text); [docs benchmarks](https://www.assemblyai.com/docs/pre-recorded-audio/benchmarks) |
| ASR (WER) | Vendor table: Universal-3.5 Pro **4.35%** avg normalized WER vs OpenAI GPT-4o Transcribe **5.338%**, ElevenLabs Scribe V2 **5.869%**, Deepgram Nova-3 **6.662%**, Azure Batch **7.02%** (selected datasets; Whisper normalizer) | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) (fetched 2026-07-24) |
| Docs English WER | Universal-3.5 Pro mean **5.6%** / median **4.9%** on their English suite (update: Jan 2026) | [Pre-recorded benchmarks](https://www.assemblyai.com/docs/pre-recorded-audio/benchmarks) |
| Joint (cpWER) | Universal-3.5 Pro **30.17%** avg cpWER across DiPCo, CALLHOME, NOTSOFAR, AMI — ahead of Azure **30.35%**, ElevenLabs **35.26%**, Speechmatics **36.6%**, Deepgram **37.93%**, Google **50.64%**. **OpenAI not listed.** | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |
| Practical | Accuracy improves with ≥ ~30 s continuous speech per speaker; `speakers_expected` is a hard constraint | [Speaker Diarization docs](https://www.assemblyai.com/docs/pre-recorded-audio/speaker-diarization) |

---

### Deepgram (Nova-3 + diarization)

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **API-combined** (ASR model + separate diarizer): enable via `diarize_model` / legacy `diarize=true` on `/v1/listen`; compatible with Nova-1/2/3, **not** Whisper | [Speaker Diarization](https://developers.deepgram.com/docs/diarization) |
| ASR claims | Nova-3 launch: median WER **6.84%** streaming / **5.26%** batch on internal multi-domain suite; large relative gains vs “next-best competitor” on *their* suite | [Introducing Nova-3](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api); [changelog 2025-02-12](https://developers.deepgram.com/changelog/2025/2/12) |
| Diarization claims | Batch Diarization **v2** (May 2026): preferred **3.3×** vs v1 in human side-by-side; ~**80%** median CER reduction on contact-center audio vs v1 — **vs Deepgram’s own prior**, not a multi-vendor DER table | [Changelog 2026-05-14](https://developers.deepgram.com/changelog/2026/5/14); [Introducing Batch Diarization V2](https://deepgram.com/learn/introducing-batch-diarization-v2) |
| Streaming diarization | Still v1; v2 is **batch-only** | Same Deepgram docs/changelog |
| Cross-vendor joint | On AssemblyAI’s cpWER table, “Deepgram” sits at **37.93%** (worse than AssemblyAI/Azure/ElevenLabs) | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |

---

### ElevenLabs Scribe

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** “smart speaker diarization” (marketing: up to 48 speakers on product pages) | [Speech to Text API](https://elevenlabs.io/speech-to-text-api); [Introducing Scribe v2](https://elevenlabs.io/blog/introducing-scribe-v2) (2026-01-09) |
| ASR claims | Original Scribe (2025-02-26): lowest WER on FLEURS & Common Voice across ~99–102 languages vs Gemini 2.0 Flash, Whisper Large V3, Deepgram Nova-3; English accuracy stated as **96.7%** (i.e. ~3.3% WER-style framing in prose) | [Meet Scribe](https://elevenlabs.io/blog/meet-scribe) |
| Scribe v2 | Batch focus; “lowest word error rate recorded on industry-standard benchmarks” (charts; long-form emphasis) | [Introducing Scribe v2](https://elevenlabs.io/blog/introducing-scribe-v2) |
| Cross-vendor | AssemblyAI WER table: Scribe V2 **5.869%** (behind Universal-3.5 and OpenAI GPT-4o Transcribe on *that* suite); cpWER **35.26%** | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |

---

### Google Cloud Speech-to-Text (Chirp 3)

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** on Chirp 3: speaker diarization GA on **`BatchRecognize` only** (not streaming); English US/UK/India among supported diarization locales | [Chirp 3 docs](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3) |
| Duration / method | BatchRecognize described as suited to ~1 minute–1 hour generally; word-level timestamps can constrain duration (docs: up to ~20 min with word-level timestamps enabled) | Same |
| Adaptation | Speech adaptation / phrase biasing GA — relevant for scripture vocabulary | Same |
| Cross-vendor joint | AssemblyAI cpWER: Google **50.64%** (weakest among serious commercial rows on that table) | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |
| Absolute WER/DER from Google | Chirp 3 docs emphasize capability and language coverage; **no** numeric multi-vendor WER/DER leaderboard in the model doc | [Chirp 3](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3) |

---

### Azure Speech

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** in batch / fast transcription (`diarization.enabled`); up to **35** speakers (error if more) | [Speech to text overview](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-to-text); [API migration notes](https://docs.azure.cn/en-us/ai-services/speech-service/migrate-2025-10-15) |
| Long audio | Batch diarization: source audio length **cannot exceed 240 minutes per file** (REST create docs) | [Batch transcription create](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-transcription-create) |
| Cross-vendor joint | AssemblyAI cpWER: Azure **30.35%** — essentially tied with Universal-3.5 Pro **30.17%** | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |
| Absolute Microsoft DER/WER | No public numeric multi-vendor DER card found in the overview docs reviewed for this note | — |

---

### AWS Transcribe

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** speaker partitioning (`ShowSpeakerLabels` / `MaxSpeakerLabels`); up to **30** speakers | [Partitioning speakers](https://docs.aws.amazon.com/transcribe/latest/dg/diarization.html); [AI Service Card](https://docs.aws.amazon.com/ai/responsible-ai/transcribe-batch-gb/overview.html) |
| Accuracy guidance | Performs best with distinct voices / limited overlap; degrades with many similar speakers or frequent interruptions — **no published DER/WER leaderboard** in those docs | Same |
| Cross-vendor | Appears in AssemblyAI code-switching WER table (weak on that task); **not** in their diarization cpWER average table | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |

---

### Rev.ai

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native by default** on async API (`monologues` with speaker IDs); optional `speakers_count` hint; multichannel `speaker_channels_count` for “perfect” channel-based separation | [Features — Speaker separation](https://docs.rev.ai/api/features); [Submit job reference](https://docs.rev.ai/api/asynchronous/reference/jobs/submittranscriptionjob.md) |
| Accuracy claims | Custom vocabulary for unusual terms; **no** public multi-vendor WER/DER numbers in features docs reviewed | Same |
| Domain fit | Custom vocabulary is explicitly aimed at out-of-dictionary terms (relevant for scripture names) | [Features — Custom vocabularies](https://docs.rev.ai/api/features) |

---

### Speechmatics

| Item | Detail | Source |
| --- | --- | --- |
| Combined ASR+diarization | **Native** batch/realtime speaker diarization (`diarization: speaker`); sensitivity / prefer-current-speaker knobs; optional speaker identification via enrollment | [Batch diarization](https://docs.speechmatics.com/speech-to-text/batch/batch-diarization.md); [Speaker identification](https://docs.speechmatics.com/speech-to-text/features/speaker-identification) |
| Accuracy claims | Config guidance (punctuation improves diarization corrections); **no** first-party numeric DER/WER leaderboard in those docs | Same |
| Cross-vendor | AssemblyAI: multilingual WER competitive (Enhanced **8.22%** global on their slice); cpWER **36.6%** | [assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks) |

---

### Open-source / self-host stacks

| Stack | Nature | Accuracy evidence | Source |
| --- | --- | --- | --- |
| **Whisper + pyannote** | **Pipeline** (ASR then diarize / align) | pyannote 3.1 publishes “Full” DER (no collar, incl. overlap), e.g. AMI headset mix **18.8%**, DIHARD 3 Full **21.7%**, VoxConverse **11.3%** | [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) / [README](https://raw.githubusercontent.com/pyannote/hf-speaker-diarization-3.1/main/README.md) |
| **WhisperX** | Pipeline: faster-whisper + wav2vec alignment + **pyannote** diarization | INTERSPEECH 2023 paper; word-level timestamps; not a single joint commercial API | [WhisperX repo](https://github.com/m-bain/whisperX); [arXiv:2303.00747](https://arxiv.org/abs/2303.00747) |
| **NVIDIA NeMo Sortformer** | End-to-end diarization + path to **joint** multi-speaker ASR supervision | Academic Sortformer results; models in NeMo | [arXiv:2409.06656](https://arxiv.org/abs/2409.06656); [NeMo diarization models](https://docs.nvidia.com/nemo-framework/user-guide/25.07/nemotoolkit/asr/speaker_diarization/models.html) |
| Recent academic bake-off | Compares pyannote 3.1, pyannoteAI, Sortformer, etc. on DER across corpora; **commercial cloud STT APIs (incl. OpenAI) not the focus** | [Benchmarking Diarization Models (arXiv:2509.26177)](https://arxiv.org/html/2509.26177v1) |

These stacks can be best-in-class on **diarization DER** under research protocols, but they are **not** drop-in substitutes for a managed combined API, and their ASR WER depends on which Whisper/NeMo ASR checkpoint is used.

---

## Snapshot tables (evidence as published — not a universal ranking)

### A. ASR-only (WER) — AssemblyAI comparative suite (vendor-run)

Lower is better. Dataset mix: synthetic medical, accented English (India), general speech, webinar. Normalization: Whisper text normalizer. **Date context:** page content as of research fetch 2026-07-24.

| Model | Avg normalized WER |
| --- | ---: |
| AssemblyAI Universal-3.5 Pro | 4.35% |
| Mistral Voxtral Mini | 5.24% |
| OpenAI GPT-4o Transcribe | 5.34% |
| ElevenLabs Scribe V2 | 5.87% |
| Deepgram Nova-3 | 6.66% |
| Azure Batch | 7.02% |

Source: [https://www.assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks)

### B. Joint transcription + speaker attribution (cpWER) — AssemblyAI suite

Datasets: DiPCo, CALLHOME, NOTSOFAR, AMI. **OpenAI `gpt-4o-transcribe-diarize` is not included.**

| Model | Avg cpWER |
| --- | ---: |
| AssemblyAI Universal-3.5 Pro | 30.17% |
| Azure | 30.35% |
| ElevenLabs Scribe V2 | 35.26% |
| Speechmatics | 36.6% |
| Deepgram | 37.93% |
| Google | 50.64% |

Source: [https://www.assemblyai.com/benchmarks](https://www.assemblyai.com/benchmarks)

### C. Native combined vs pipeline

| System | Combined offering |
| --- | --- |
| OpenAI `gpt-4o-transcribe-diarize` | Native joint model |
| AssemblyAI Universal + `speaker_labels` | Native (joint transcript+speaker model claimed for Universal-3.5) |
| ElevenLabs Scribe | Native diarization in STT API |
| Google Chirp 3 | Native diarization (batch) |
| Azure Speech | Native diarization (batch/fast) |
| AWS Transcribe | Native speaker labels |
| Rev.ai | Native (default on async) |
| Speechmatics | Native speaker mode |
| Deepgram Nova-3 + `diarize_model` | Combined API; **separate** diarizer versions |
| WhisperX / Whisper+pyannote / NeMo | Explicit **pipelines** (or research joint training), self-hosted |

---

## What the evidence supports

1. **OpenAI is a credible modern ASR vendor.** First-party claims show `gpt-4o-transcribe` improves WER vs Whisper on FLEURS/Common Voice ([OpenAI announcement](https://openai.com/index/introducing-our-next-generation-audio-models/)). AssemblyAI’s comparative English-ish suite places GPT-4o Transcribe near the top but **behind** Universal-3.5 Pro.
2. **OpenAI offers a true native diarized transcription API** (`gpt-4o-transcribe-diarize` + `diarized_json`), which matches SermonRecorder’s need for speaker-attributed segments ([docs](https://developers.openai.com/api/docs/guides/speech-to-text)).
3. **On published joint metrics, other vendors currently look stronger — with caveats.** AssemblyAI’s cpWER leaderboard (vendor-run) puts Universal-3.5 Pro and Azure ahead of ElevenLabs, Speechmatics, Deepgram, and Google, and **omits OpenAI diarize entirely**.
4. **ASR “who is #1?” depends on the benchmark.** ElevenLabs claims FLEURS/Common Voice leadership ([Meet Scribe](https://elevenlabs.io/blog/meet-scribe)); Deepgram claims Nova-3 leadership on its internal domain suite ([Nova-3](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api)); AssemblyAI claims leadership on its suites ([benchmarks](https://www.assemblyai.com/benchmarks)). These cannot all be absolute truth simultaneously.
5. **Open-source diarizers remain scientifically strong on DER** (pyannote 3.1 published Full DER tables), but combining them with Whisper is a **pipeline**, not proven superior end-to-end WER+cpWER vs 2026 cloud joint models without your own eval.

## What the evidence does **not** support

1. **That OpenAI is the most accurate combined STT+diarization system today** — unsupported; key metrics unpublished for `-diarize`, and no inclusive head-to-head found.
2. **That OpenAI is clearly worse than everyone on diarization** — also unsupported; absence from tables ≠ measured last place.
3. **Transfer of meeting/telephony benchmarks to sermons** — DiPCo / AMI / CALLHOME / contact-center CER are imperfect proxies for pulpit monologue + occasional second speakers, room mic, music, and religious lexicon.
4. **Using list prices as a proxy for accuracy** — ignored except where cited for context.

---

## Recommendation (accuracy-first, sermon-length English, no code changes)

**Do not treat the current OpenAI default as proven “best accuracy.”** Treat it as a **reasonable, native diarizing API** that already fits the product’s chunking architecture, with known accuracy risks for this domain:

- No prompt/biasing on `-diarize` for scripture names ([OpenAI docs](https://developers.openai.com/api/docs/guides/speech-to-text)).
- Long sermons require chunking (25 MB / likely duration caps), which can hurt cross-chunk speaker consistency (SermonRecorder already predominant-speaker-per-chunk).

**Accuracy-first shortlist for a private bake-off on representative pew audio (20–60+ min English sermons):**

1. **OpenAI `gpt-4o-transcribe-diarize`** (baseline; optionally test known-speaker references for the preacher).
2. **AssemblyAI Universal-3.5 Pro + `speaker_labels`** (strongest *published* joint cpWER claim; allow `speakers_expected` ≈ 1–3 for typical services).
3. **Azure Speech batch diarization** (nearly tied with AssemblyAI on that cpWER table; 240-minute file headroom).
4. **ElevenLabs Scribe v2** (strong multilingual/long-form ASR claims; native diarization; keyterm prompting for vocabulary).
5. **Optional:** Deepgram Nova-3 + `diarize_model=v2` (strong self-reported ASR; diarization improved vs own v1; weaker on AssemblyAI cpWER).
6. **Optional research path:** Whisper large-v3 / faster-whisper + pyannote 3.1 or WhisperX if self-hosting and DER-first experimentation matter more than managed ops.

**Eval method:** Prefer **cpWER or word-level speaker attribution error** on a small human-labeled sermon set (plus plain WER), rather than trusting any vendor’s marketing table alone. Include clips with scripture reading, second speakers (worship leader / congregation responses), and noisy room mics.

Until that bake-off exists, the honest accuracy statement is: **OpenAI is competitive on ASR and convenient for native diarization, but not demonstrably the most accurate combined option available in mid-2026.**

---

## Sources

### OpenAI
- [Speech to text guide](https://developers.openai.com/api/docs/guides/speech-to-text) — models, 25 MB limit, diarize requirements, no prompting on `-diarize`
- [gpt-4o-transcribe-diarize model page](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize)
- [Create transcription API reference](https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create/)
- [Introducing next-generation audio models](https://openai.com/index/introducing-our-next-generation-audio-models/) — WER claims vs Whisper
- [Developer community: 1500 s duration](https://community.openai.com/t/gpt4-0-transcribe-max-1500-seconds/1306684) — operational limit reports

### AssemblyAI
- [Benchmarks (interactive / tables)](https://www.assemblyai.com/benchmarks) — WER & cpWER comparisons (fetched 2026-07-24)
- [Pre-recorded audio benchmarks docs](https://www.assemblyai.com/docs/pre-recorded-audio/benchmarks) — Jan 2026 English WER
- [Speaker Diarization docs](https://www.assemblyai.com/docs/pre-recorded-audio/speaker-diarization)
- [How accurate is speech-to-text in 2026?](https://www.assemblyai.com/blog/how-accurate-speech-to-text)
- [Speaker diarization improvements (cpWER/DER explanation)](https://www.assemblyai.com/blog/speaker-diarization-improvements)

### Deepgram
- [Introducing Nova-3](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api)
- [Changelog: Nova-3 (2025-02-12)](https://developers.deepgram.com/changelog/2025/2/12)
- [Speaker Diarization docs](https://developers.deepgram.com/docs/diarization)
- [Changelog: Batch Diarization v2 (2026-05-14)](https://developers.deepgram.com/changelog/2026/5/14)
- [Introducing Batch Diarization V2](https://deepgram.com/learn/introducing-batch-diarization-v2)

### ElevenLabs
- [Meet Scribe (2025-02-26)](https://elevenlabs.io/blog/meet-scribe)
- [Introducing Scribe v2 (2026-01-09)](https://elevenlabs.io/blog/introducing-scribe-v2)
- [Speech to Text API product page](https://elevenlabs.io/speech-to-text-api)

### Google Cloud
- [Chirp 3 Transcription](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3)
- [Speech-to-Text release notes](https://docs.cloud.google.com/speech-to-text/docs/release-notes)

### Azure
- [Speech to text overview](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-to-text)
- [Batch transcription create (240 min diarization limit)](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-transcription-create)
- [REST API 2025-10-15 migration / diarization schema](https://docs.azure.cn/en-us/ai-services/speech-service/migrate-2025-10-15)

### AWS
- [Partitioning speakers (diarization)](https://docs.aws.amazon.com/transcribe/latest/dg/diarization.html)
- [Amazon Transcribe AI Service Card](https://docs.aws.amazon.com/ai/responsible-ai/transcribe-batch-gb/overview.html)

### Rev.ai
- [Features (diarization, custom vocabulary)](https://docs.rev.ai/api/features)
- [Submit transcription job](https://docs.rev.ai/api/asynchronous/reference/jobs/submittranscriptionjob.md)
- [Best practices (multi-channel)](https://docs.rev.ai/api/asynchronous/best-practices)

### Speechmatics
- [Batch diarization](https://docs.speechmatics.com/speech-to-text/batch/batch-diarization.md)
- [Speaker identification](https://docs.speechmatics.com/speech-to-text/features/speaker-identification)

### Open source / academic
- [pyannote speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [WhisperX](https://github.com/m-bain/whisperX) / [arXiv:2303.00747](https://arxiv.org/abs/2303.00747)
- [Sortformer arXiv:2409.06656](https://arxiv.org/abs/2409.06656)
- [NeMo speaker diarization models](https://docs.nvidia.com/nemo-framework/user-guide/25.07/nemotoolkit/asr/speaker_diarization/models.html)
- [Benchmarking Diarization Models arXiv:2509.26177](https://arxiv.org/html/2509.26177v1)

### Product context (this repo)
- `backend/config/settings.py` — `OPENAI_TRANSCRIPTION_MODEL` default
- [ADR 0003](../adr/0003-simpleai-artifacts-custom-transcription.md)
