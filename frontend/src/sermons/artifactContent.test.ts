import { describe, expect, it } from 'vitest'
import {
  parseDoctrinalReview,
  parseHymn,
  parseQuiz,
  parseRelatedSources,
  parseTuneSuggestions,
} from './artifactContent'
import { ownerSermonSections, sharedSermonSections } from './sections'

describe('generated artifact content', () => {
  it('parses a metered hymn into its heading and verses', () => {
    const hymn = parseHymn(`Title: Grace Has Brought Us Home
Meter: CM (8.6.8.6)

1.
The child had wandered far
Yet home remained in view
The father ran with open arms
And made the lost one new

2.
O grace that welcomes home
Teach us to welcome too
To cross the road with open arms
As Christ has taught us to`)

    expect(hymn.title).toBe('Grace Has Brought Us Home')
    expect(hymn.meter).toBe('CM (8.6.8.6)')
    expect(hymn.verses).toHaveLength(2)
    expect(hymn.verses[0]).toHaveLength(4)
  })

  it('parses compatible tune names and their traditions', () => {
    expect(
      parseTuneSuggestions(
        'HYFRYDOL — Anglican, Methodist, and Catholic hymnals\nBEECHER — Methodist and Anglican hymnals',
      ),
    ).toEqual([
      {
        name: 'HYFRYDOL',
        traditions: 'Anglican, Methodist, and Catholic hymnals',
      },
      {
        name: 'BEECHER',
        traditions: 'Methodist and Anglican hymnals',
      },
    ])
  })

  it('keeps quiz questions paired with their answers', () => {
    expect(
      parseQuiz(
        'Q1. What did the father do?\nA1. He welcomed his son.\n\nQ2. What is the invitation?\nA2. Receive grace.',
      ),
    ).toEqual([
      {
        question: 'What did the father do?',
        answer: 'He welcomed his son.',
      },
      {
        question: 'What is the invitation?',
        answer: 'Receive grace.',
      },
    ])
  })

  it('orders owner tabs Study → Transcript → Discuss → Reflect → Feedback', () => {
    expect(ownerSermonSections).toEqual([
      ['study', 'Study'],
      ['transcript', 'Transcript'],
      ['discuss', 'Discuss'],
      ['reflection', 'Reflect'],
      ['feedback', 'Feedback'],
    ])
  })

  it('hides Hymn and Reflect from public tabs', () => {
    expect(sharedSermonSections).toEqual([
      ['study', 'Study'],
      ['transcript', 'Transcript'],
      ['discuss', 'Discuss'],
      ['feedback', 'Feedback'],
    ])
    expect(sharedSermonSections.map(([id]) => id)).not.toContain('hymn')
    expect(ownerSermonSections.map(([id]) => id)).not.toContain('hymn')
  })

  it('parses related sources JSON', () => {
    expect(
      parseRelatedSources(
        JSON.stringify({
          sources: [
            {
              title: 'Deus Caritas Est',
              author: 'Benedict XVI',
              year: '2005',
              excerpt: 'God is love.',
              source_url: 'https://example.com/dce',
              category: 'magisterial',
              query: 'Catholic teaching on love',
            },
          ],
        }),
      ),
    ).toEqual([
      {
        title: 'Deus Caritas Est',
        author: 'Benedict XVI',
        year: '2005',
        excerpt: 'God is love.',
        source_url: 'https://example.com/dce',
        category: 'magisterial',
        query: 'Catholic teaching on love',
      },
    ])
  })

  it('parses doctrinal review findings', () => {
    const review = parseDoctrinalReview(
      JSON.stringify({
        findings: [
          {
            assertion: 'Faith alone saves without charity.',
            severity: 'borderline',
            explanation: 'Catholic teaching holds faith working through love.',
            citations: [
              {
                document_title: 'Catechism of the Catholic Church',
                document_author: '',
                document_year: '',
                document_reference: '1815',
                cited_text: 'The gift of faith remains...',
                source_url: '',
              },
            ],
          },
        ],
        summary: '',
        citations: [],
      }),
    )
    expect(review.findings).toHaveLength(1)
    expect(review.findings[0]?.severity).toBe('borderline')
    expect(review.findings[0]?.citations[0]?.document_reference).toBe('1815')
  })
})
