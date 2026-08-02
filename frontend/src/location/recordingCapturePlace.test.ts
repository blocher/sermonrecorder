import { describe, expect, it } from 'vitest'

import { recordingCapturePlace } from './recordingCapturePlace'

describe('recordingCapturePlace', () => {
  it('reads the place captured with the recording', () => {
    expect(
      recordingCapturePlace({
        capture_latitude: '40.001000',
        capture_longitude: '-75.002000',
      }),
    ).toEqual({ latitude: 40.001, longitude: -75.002 })
  })

  it('returns null when the recording has no stored place', () => {
    expect(
      recordingCapturePlace({
        capture_latitude: null,
        capture_longitude: null,
      }),
    ).toBeNull()
  })

  it('rejects a half-complete coordinate pair', () => {
    expect(
      recordingCapturePlace({
        capture_latitude: '40.001000',
        capture_longitude: null,
      }),
    ).toBeNull()
  })
})
