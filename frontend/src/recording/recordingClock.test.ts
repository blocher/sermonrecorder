import { afterEach, describe, expect, it } from 'vitest'
import {
  clearRecordingStartedAt,
  elapsedSecondsSince,
  loadRecordingStartedAt,
  persistRecordingStartedAt,
} from './recordingClock'

afterEach(() => {
  clearRecordingStartedAt()
})

describe('recordingClock', () => {
  it('computes elapsed seconds from wall-clock timestamps', () => {
    expect(elapsedSecondsSince(1_000, 6_500)).toBe(5)
    expect(elapsedSecondsSince(1_000, 999)).toBe(0)
  })

  it('persists and restores the recording start time across unlock', () => {
    persistRecordingStartedAt(1_700_000_000_000)
    expect(loadRecordingStartedAt()).toBe(1_700_000_000_000)
    clearRecordingStartedAt()
    expect(loadRecordingStartedAt()).toBeUndefined()
  })
})
