export interface HymnContent {
  title: string
  meter: string
  verses: string[][]
}

export interface TuneSuggestion {
  name: string
  traditions: string
}

export interface QuizItem {
  question: string
  answer: string
}

export interface RelatedSource {
  title: string
  author: string
  year: string
  excerpt: string
  source_url: string
  category: string
  query: string
}

export interface DoctrinalCitation {
  document_title: string
  document_author: string
  document_year: string
  document_reference: string
  cited_text: string
  source_url: string
}

export interface DoctrinalFinding {
  assertion: string
  severity: 'heretical' | 'borderline' | string
  explanation: string
  citations: DoctrinalCitation[]
}

export interface DoctrinalReview {
  findings: DoctrinalFinding[]
  summary: string
  citations: DoctrinalCitation[]
}

export function numberedItems(content: string): string[] {
  return content
    .split(/\n+/)
    .map((item) => item.replace(/^\s*\d+\.\s*/, '').trim())
    .filter(Boolean)
}

export interface OutlinePoint {
  text: string
  start_seconds: number | null
}

/** Outline lines may include `[M:SS]` / `[H:MM:SS]` after the number for seekable points. */
export function parseOutlinePoints(content: string): OutlinePoint[] {
  return content
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(
        /^\d+\.\s*(?:\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*)?(.*)$/,
      )
      if (!match) {
        return { text: line.replace(/^\d+\.\s*/, '').trim(), start_seconds: null }
      }
      const [, first, second, third, text] = match
      const pointText = (text ?? '').trim()
      if (!pointText) return null
      if (first == null || second == null) {
        return { text: pointText, start_seconds: null }
      }
      const hours = third != null ? Number(first) : 0
      const minutes = third != null ? Number(second) : Number(first)
      const seconds = third != null ? Number(third) : Number(second)
      if (
        !Number.isFinite(hours) ||
        !Number.isFinite(minutes) ||
        !Number.isFinite(seconds)
      ) {
        return { text: pointText, start_seconds: null }
      }
      return {
        text: pointText,
        start_seconds: hours * 3600 + minutes * 60 + seconds,
      }
    })
    .filter((point): point is OutlinePoint => point != null)
}

export function quotationItems(content: string): string[] {
  const quotePairs = new Set(['""', '“”', '‘’'])
  return content
    .split(/\n+/)
    .map((item) => item.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim())
    .map((item) =>
      item.length >= 2 && quotePairs.has(`${item[0]}${item.at(-1)}`)
        ? item.slice(1, -1).trim()
        : item,
    )
    .filter(Boolean)
}

export function paragraphs(content: string): string[] {
  return content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
}

export function parseHymn(content: string): HymnContent {
  const blocks = paragraphs(content)
  const heading = blocks.shift()?.split(/\n/) ?? []
  const title = heading.find((line) => /^Title:\s*/i.test(line))?.replace(/^Title:\s*/i, '') ?? ''
  const meter = heading.find((line) => /^Meter:\s*/i.test(line))?.replace(/^Meter:\s*/i, '') ?? ''
  const verses = blocks
    .map((block) =>
      block
        .split(/\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .filter((line, index) => index !== 0 || !/^\d+[.)]$/.test(line)),
    )
    .filter((verse) => verse.length)

  return { title, meter, verses }
}

export function parseTuneSuggestions(content: string): TuneSuggestion[] {
  return content
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, ...traditions] = line.split(/\s+—\s+/)
      return {
        name: name?.trim() ?? '',
        traditions: traditions.join(' — ').trim(),
      }
    })
    .filter((suggestion) => suggestion.name)
}

export function parseQuiz(content: string): QuizItem[] {
  return paragraphs(content)
    .map((block) => {
      const lines = block
        .split(/\n/)
        .map((line) => line.trim())
        .filter(Boolean)
      const question = lines.shift()?.replace(/^Q\d+[.)]\s*/i, '').trim() ?? ''
      const answer = lines.join(' ').replace(/^A\d+[.)]\s*/i, '').trim()
      return { question, answer }
    })
    .filter((item) => item.question && item.answer)
}

function readJsonObject(content: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(content)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function parseCitation(value: unknown): DoctrinalCitation | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const item = value as Record<string, unknown>
  const citation: DoctrinalCitation = {
    document_title: asString(item.document_title),
    document_author: asString(item.document_author),
    document_year: asString(item.document_year),
    document_reference: asString(item.document_reference),
    cited_text: asString(item.cited_text),
    source_url: asString(item.source_url),
  }
  return citation.document_title || citation.cited_text || citation.source_url
    ? citation
    : null
}

export function parseRelatedSources(content: string): RelatedSource[] {
  const payload = readJsonObject(content)
  const sources = payload?.sources
  if (!Array.isArray(sources)) return []
  return sources
    .map((value) => {
      if (!value || typeof value !== 'object' || Array.isArray(value)) return null
      const item = value as Record<string, unknown>
      const source: RelatedSource = {
        title: asString(item.title) || 'Untitled source',
        author: asString(item.author),
        year: asString(item.year),
        excerpt: asString(item.excerpt),
        source_url: asString(item.source_url),
        category: asString(item.category),
        query: asString(item.query),
      }
      return source
    })
    .filter((source): source is RelatedSource => Boolean(source))
}

export function parseDoctrinalReview(content: string): DoctrinalReview {
  const payload = readJsonObject(content)
  if (!payload) {
    return { findings: [], summary: content.trim(), citations: [] }
  }
  const findings = Array.isArray(payload.findings)
    ? payload.findings
        .map((value) => {
          if (!value || typeof value !== 'object' || Array.isArray(value)) return null
          const item = value as Record<string, unknown>
          const citations = Array.isArray(item.citations)
            ? item.citations
                .map(parseCitation)
                .filter((citation): citation is DoctrinalCitation => Boolean(citation))
            : []
          const finding: DoctrinalFinding = {
            assertion: asString(item.assertion),
            severity: asString(item.severity) || 'borderline',
            explanation: asString(item.explanation),
            citations,
          }
          return finding.assertion || finding.explanation ? finding : null
        })
        .filter((finding): finding is DoctrinalFinding => Boolean(finding))
    : []
  const citations = Array.isArray(payload.citations)
    ? payload.citations
        .map(parseCitation)
        .filter((citation): citation is DoctrinalCitation => Boolean(citation))
    : []
  return {
    findings,
    summary: asString(payload.summary),
    citations,
  }
}
