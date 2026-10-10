export const registrationRules = {
  username: '3–32 位，支持中文',
  password: '至少 8 位',
  confirmation: '',
}

export type RegistrationField = keyof typeof registrationRules
export const usernamePattern = '[A-Za-z0-9_\\-\\u4e00-\\u9fff]{3,32}'
export const validUsername = (value: string) => new RegExp(`^${usernamePattern}$`, 'u').test(value)

export function validateRegistration(username: string, password: string, confirmation: string) {
  const errors = {
    username: !username ? '请填写用户名' : valueLengthError(username) || (validUsername(username) ? '' : '请用中文、字母、数字、下划线或连字符'),
    password: !password ? '请填写密码' : password.length < 8 ? '密码至少 8 位' : password.length > 128 ? '密码最多 128 位' : '',
    confirmation: !confirmation ? '请再次输入密码' : confirmation === password ? '' : '两次密码不一致',
  }
  const valid = Object.values(errors).every(error => !error)
  return { errors, valid }
}

function valueLengthError(value: string) {
  return value.length < 3 || value.length > 32 ? '用户名需为 3–32 位' : ''
}
