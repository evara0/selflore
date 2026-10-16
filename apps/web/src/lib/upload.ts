import { ApiError, type Attachment } from './workspace'

export type UploadLimits = {
  max_bytes: number
  max_pixels: number
  max_edge: number
  max_images: number
  is_available: boolean
  formats: string[]
}

export async function uploadImage(
  file: File,
  requestId: string,
  token: string,
  onProgress: (n: number) => void,
  signal?: AbortSignal,
): Promise<Attachment> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  const form = new FormData()
  form.append('file', file)
  form.append('client_request_id', requestId)
  form.append(
    'file_sha256',
    [...new Uint8Array(digest)].map((n) => n.toString(16).padStart(2, '0')).join(''),
  )
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    xhr.open('POST', '/api/attachments')
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', token)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onerror = () => {
      signal?.removeEventListener('abort', abort)
      reject(new Error('图片上传网络失败，请重试'))
    }
    xhr.onabort = () => {
      signal?.removeEventListener('abort', abort)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    xhr.onload = () => {
      signal?.removeEventListener('abort', abort)
      let result
      try {
        result = JSON.parse(xhr.responseText)
      } catch {
        reject(new Error('上传响应无效'))
        return
      }
      if (xhr.status === 401) window.dispatchEvent(new Event('session-expired'))
      if (xhr.status < 200 || xhr.status >= 300)
        reject(new ApiError(result.detail?.message || '图片上传失败', xhr.status))
      else resolve(result)
    }
    signal?.addEventListener('abort', abort, { once: true })
    xhr.send(form)
  })
}
