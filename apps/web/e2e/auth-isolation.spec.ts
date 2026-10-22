import { test, expect } from './fixtures'
import { randomUUID } from 'node:crypto'

test('registration limit still applies inside each isolated browser case', async ({ request }) => {
  const base = process.env.SELFLORE_BROWSER_BASE_URL || 'http://127.0.0.1:24568'
  for (let i = 0; i < 6; i++) {
    const response = await request.post(base + '/api/auth/register', {
      headers: { Origin: base },
      data: { username: 'limit_' + randomUUID().slice(0, 8), password: 'isolated-limit-test-123' },
    })
    expect(response.status()).toBe(i < 5 ? 201 : 429)
  }
})
