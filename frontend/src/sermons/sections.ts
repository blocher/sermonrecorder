export type SermonSection =
  | 'study'
  | 'transcript'
  | 'discuss'
  | 'reflection'
  | 'feedback'
  | 'hymn'

/** Visible tabs for shared/public views. Hymn is still generated but hidden for now. */
export const sharedSermonSections: readonly [SermonSection, string][] = [
  ['study', 'Study'],
  ['transcript', 'Transcript'],
  ['discuss', 'Discuss'],
  ['feedback', 'Feedback'],
]

export const ownerSermonSections: readonly [SermonSection, string][] = [
  ['study', 'Study'],
  ['transcript', 'Transcript'],
  ['discuss', 'Discuss'],
  ['reflection', 'Reflect'],
  ['feedback', 'Feedback'],
]
