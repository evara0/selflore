import { expect, test } from 'vitest'
import { validateRegistration } from './registration'

const password = 'a'.repeat(8)

test.each([
  ['ab', false], ['abc', true], ['a'.repeat(32), true], ['a'.repeat(33), false],
  ['1abc', true], ['中文名字', true], ['123', true], ['_ab', true], ['-ab', true], ['a.b', false], ['a b', false], ['用户😀', false],
  ['AbC_123-', true], ['', false],
])('username %s validity is %s', (username, valid) => {
  expect(!validateRegistration(username, password, password).errors.username).toBe(valid)
})

test.each([0, 7, 8, 128, 129])('password length %i respects relaxed limits', length => {
  const value = 'a'.repeat(length)
  expect(validateRegistration('alice', value, value).valid).toBe(length >= 8 && length <= 128)
})

test('confirmation is required and compares the exact password without trimming', () => {
  expect(validateRegistration('alice', password, '').errors.confirmation).toBe('请再次输入密码')
  expect(validateRegistration('alice', password, password + ' ').errors.confirmation).toBe('两次密码不一致')
  expect(validateRegistration('alice', ' '.repeat(12), ' '.repeat(12)).valid).toBe(true)
  expect(validateRegistration('', '', '').valid).toBe(false)
  expect(validateRegistration('alice', password, password).valid).toBe(true)
})
