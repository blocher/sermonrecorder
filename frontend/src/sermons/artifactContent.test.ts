import { describe, expect, it } from 'vitest'
import { parseHymn, parseQuiz, parseTuneSuggestions } from './artifactContent'
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

  it('keeps public tabs aligned with the owner view except for Reflection', () => {
    expect(ownerSermonSections.slice(0, -1)).toEqual(sharedSermonSections)
    expect(ownerSermonSections.at(-1)).toEqual(['reflection', 'Reflect'])
  })
})
