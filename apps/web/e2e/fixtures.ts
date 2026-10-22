import { test as base } from '@playwright/test'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import path from 'node:path'

export { expect } from '@playwright/test'
export type { Page } from '@playwright/test'

const run = promisify(execFile)

export const test = base.extend<{ registrationIsolation: void }>({
  registrationIsolation: [
    async ({ baseURL }, use) => {
      if (process.env.SELFLORE_TEST_ISOLATED !== '1')
        throw new Error('Real API browser cases require an explicit disposable environment')
      if (baseURL !== 'http://127.0.0.1:24568')
        throw new Error('Real API browser cases require the fixed disposable loopback service')
      const api = path.resolve('../api')
      const python = path.join(api, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
      await run(python, ['-B', path.resolve('../../scripts/reset_browser_registration.py')], {
        cwd: api,
        timeout: 15000,
        windowsHide: true,
      })
      await use()
    },
    { auto: true },
  ],
})
