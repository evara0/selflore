import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', workers: 1, fullyParallel: false,
  use: { baseURL: process.env.SELFLORE_BROWSER_BASE_URL || 'http://127.0.0.1:24568', channel: 'chrome', hasTouch: true, trace: 'retain-on-failure' },
  outputDir: '../../.cache/card-tests/browser-results',
  reporter: [['list']],
})
