export type SermonSection =
  | 'study'
  | 'feedback'
  | 'hymn'
  | 'discuss'
  | 'transcript'
  | 'reflection'

export const sharedSermonSections: readonly [SermonSection, string][] = [
  ['study', 'Study'],
  ['feedback', 'Feedback'],
  ['hymn', 'Hymn'],
  ['discuss', 'Discuss'],
  ['transcript', 'Transcript'],
]

export const ownerSermonSections: readonly [SermonSection, string][] = [
  ...sharedSermonSections,
  ['reflection', 'Reflect'],
]
