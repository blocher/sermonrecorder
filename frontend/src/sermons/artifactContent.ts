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

export function numberedItems(content: string): string[] {
  return content
    .split(/\n+/)
    .map((item) => item.replace(/^\s*\d+\.\s*/, '').trim())
    .filter(Boolean)
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
