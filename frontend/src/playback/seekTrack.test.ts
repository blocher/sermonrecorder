import { describe, expect, it } from 'vitest'
import { formatClock, parseClock, seekRatioFromClientX } from './seekTrack'

describe('seekTrack', () => {
  it('maps pointer position to a clamped seek ratio', () => {
    const track = {
      getBoundingClientRect: () => ({ left: 100, width: 200 }),
    } as HTMLElement

    expect(seekRatioFromClientX(track, 100)).toBe(0)
    expect(seekRatioFromClientX(track, 200)).toBe(0.5)
    expect(seekRatioFromClientX(track, 300)).toBe(1)
    expect(seekRatioFromClientX(track, 50)).toBe(0)
    expect(seekRatioFromClientX(track, 400)).toBe(1)
  })

  it('formats and parses regenerate clock values', () => {
    expect(formatClock(0)).toBe('00:00')
    expect(formatClock(125)).toBe('02:05')
    expect(formatClock(3723)).toBe('1:02:03')
    expect(parseClock('02:05')).toBe(125)
    expect(parseClock('1:02:03')).toBe(3723)
    expect(parseClock('02:65')).toBeNull()
    expect(parseClock('nope')).toBeNull()
  })
})
