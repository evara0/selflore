import { expect, test } from 'vitest'
import { cardInk, cardInks, collectionInk } from './theme'

test('content ink is reproducible across identity formatting, order and metadata changes', () => {
  const cards = Array.from({ length: 20 }, (_, i) => ({
    id: `de000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
    title: `标题 ${i}`,
  }))
  const initial = new Map(cards.map((card) => [card.id, cardInk(card.id)]))
  for (const card of cards.reverse().map((card) => ({ ...card, title: '已修改' }))) {
    expect(cardInk(` ${card.id.toUpperCase()} `)).toBe(initial.get(card.id))
    expect(cardInks).toContain(cardInk(card.id))
  }
  expect(new Set(initial.values()).size).toBe(4)
  expect(cardInk('hello')).toBe('orange')
})

test('unsaved content has a fixed fallback and existing collection choices remain compatible', () => {
  expect(cardInk()).toBe('purple')
  expect(cardInk(null)).toBe('purple')
  expect(cardInk('  ')).toBe('purple')
  expect(collectionInk('hello', 'sage')).toBe('green')
  expect(collectionInk('hello', 'clay')).toBe('orange')
  expect(collectionInk('hello', 'unknown')).toBe(cardInk('hello'))
})
