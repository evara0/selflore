export const cardInks = ['purple', 'blue', 'green', 'orange'] as const
export type CardInk = typeof cardInks[number]

/** The content identity, rather than its position or review unit, owns its ink. */
export function cardInk(id?: string | null): CardInk {
  const identity = id?.trim().toLowerCase()
  if (!identity) return cardInks[0]
  let hash = 0x811c9dc5
  for (let i = 0; i < identity.length; i++) {
    hash = Math.imul(hash ^ identity.charCodeAt(i), 0x01000193) >>> 0
  }
  return cardInks[hash % cardInks.length]
}

export function collectionInk(id: string, coverColor: string): CardInk {
  return coverColor === 'sage' ? 'green' : coverColor === 'clay' ? 'orange' : cardInk(id)
}
