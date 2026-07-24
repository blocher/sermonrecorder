export type SermonSection = 'study' | 'hymn' | 'discuss' | 'transcript' | 'reflection'

export const sharedSermonSections: readonly [SermonSection, string][] = [
  ['study', 'Study'],
  ['hymn', 'Hymn'],
  ['discuss', 'Discuss'],
  ['transcript', 'Transcript'],
]

export const ownerSermonSections: readonly [SermonSection, string][] = [
  ...sharedSermonSections,
  ['reflection', 'Reflect'],
]
