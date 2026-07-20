export interface TranscriptSegment {
  time: string
  seconds: number
  text: string
}

export interface Sermon {
  id: string
  title: string
  date: string
  preacher: string
  church: string
  occasion: string
  liturgicalDay: string
  duration: string
  excerpt: string
  tags: string[]
  scripture: string[]
  shortSummary: string
  longSummary: string[]
  outline: string[]
  adultQuestions: string[]
  kidsQuestions: string[]
  transcript: TranscriptSegment[]
  reflection?: string
}

export const sermons: Sermon[] = [
  {
    id: 'come-and-rest',
    title: 'Come to Me and Rest',
    date: 'June 28, 2026',
    preacher: 'Fr. Daniel Ortiz',
    church: 'St. Anselm Church',
    occasion: 'Sunday',
    liturgicalDay: 'Thirteenth Sunday in Ordinary Time',
    duration: '32 min',
    excerpt:
      'Rest is not the absence of responsibility. It is the freedom to carry what is ours without pretending that we carry it alone.',
    tags: ['rest', 'discipleship', 'grace'],
    scripture: ['Matthew 11:28–30', 'Psalm 62:5–8'],
    shortSummary:
      'Jesus does not promise a life without weight. He offers a shared yoke: a way of carrying ordinary duties without being ruled by fear, self-sufficiency, or the need to prove ourselves.',
    longSummary: [
      'The sermon begins with the exhaustion many people hide beneath competence. Our calendars may be full of good things, yet we can still carry them as though every outcome depends on us.',
      'Jesus’ invitation to take his yoke is not an escape from responsibility. A yoke joins two lives in one movement. Christian rest grows as we learn which burdens are ours to carry, which belong to our neighbors, and which must be returned to God.',
      'The preacher closes with a practical invitation: name one burden before evening prayer, then ask what faithful action belongs to today rather than rehearsing every possible tomorrow.',
    ],
    outline: [
      'The fatigue beneath competence',
      'A yoke means shared weight',
      'Gentleness as strength under direction',
      'The grace of today’s responsibility',
    ],
    adultQuestions: [
      'Which responsibility have you been carrying as if its outcome depends entirely on you?',
      'What would faithful action look like if you released the need to control the result?',
      'Where have you mistaken exhaustion for faithfulness?',
    ],
    kidsQuestions: [
      'What is something that feels heavy or worrying this week?',
      'Who helps you carry hard things?',
      'What could you tell Jesus about before you go to sleep?',
    ],
    transcript: [
      {
        time: '00:00',
        seconds: 0,
        text: 'There is a kind of tiredness that sleep alone cannot answer. It comes when we believe that every good thing depends on us holding it together.',
      },
      {
        time: '03:42',
        seconds: 222,
        text: 'Jesus does not say, “Come to me and you will never carry anything again.” He says, “Take my yoke.” That is a very different promise.',
      },
      {
        time: '08:16',
        seconds: 496,
        text: 'A yoke joins two lives in one direction. The weight is still real, but it is no longer solitary.',
      },
      {
        time: '14:08',
        seconds: 848,
        text: 'Gentleness is not passivity. It is strength that no longer needs to prove itself by force.',
      },
      {
        time: '21:34',
        seconds: 1294,
        text: 'Some burdens are ours to carry. Some belong to our neighbor. Some have been held so tightly that we have forgotten they belong to God.',
      },
      {
        time: '28:51',
        seconds: 1731,
        text: 'Before evening prayer, name one burden. Ask: what is the faithful thing for today? Then let tomorrow remain where God has placed it.',
      },
    ],
    reflection:
      'I keep treating preparation as a way to guarantee the outcome. This week I want to prepare faithfully, then stop rehearsing what everyone might think.',
  },
  {
    id: 'mercy-at-the-table',
    title: 'Mercy at the Table',
    date: 'June 14, 2026',
    preacher: 'Rev. Miriam Cho',
    church: 'Grace Anglican Parish',
    occasion: 'Sunday',
    liturgicalDay: 'Second Sunday after Pentecost',
    duration: '27 min',
    excerpt:
      'Hospitality begins before the door opens. It begins when we stop deciding who is likely to deserve a place.',
    tags: ['mercy', 'hospitality', 'belonging'],
    scripture: ['Luke 14:12–24'],
    shortSummary:
      'The kingdom’s table is not built around social usefulness. Christian hospitality makes room before it knows what can be returned.',
    longSummary: [],
    outline: [],
    adultQuestions: [],
    kidsQuestions: [],
    transcript: [],
  },
  {
    id: 'mustard-seed-courage',
    title: 'Mustard Seed Courage',
    date: 'May 31, 2026',
    preacher: 'Fr. Daniel Ortiz',
    church: 'St. Anselm Church',
    occasion: 'Feast',
    liturgicalDay: 'Trinity Sunday',
    duration: '36 min',
    excerpt:
      'Courage is rarely loud at first. Often it is one faithful act small enough to do before fear finishes speaking.',
    tags: ['courage', 'faith', 'vocation'],
    scripture: ['Matthew 13:31–32', 'Romans 5:1–5'],
    shortSummary:
      'Small acts of trust train us to recognize grace. The kingdom often begins below the threshold of what the world calls impressive.',
    longSummary: [],
    outline: [],
    adultQuestions: [],
    kidsQuestions: [],
    transcript: [],
  },
]

export function getSermon(id: string): Sermon {
  return sermons.find((sermon) => sermon.id === id) ?? sermons[0]
}
