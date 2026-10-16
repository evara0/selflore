import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { useData, useIdentity, type Attachment } from '../lib/workspace'
import { uploadImage, type UploadLimits } from '../lib/upload'
import { PrivateImage } from './Attachments'

type Attempt = {
  key: string
  file: File
  progress: number
  error?: string
  controller: AbortController
}
export type ImageUploaderHandle = { addFiles: (files: File[]) => void }
type Props = {
  images: Attachment[]
  onChange: (images: Attachment[]) => void
  onBusy: (busy: boolean) => void
}
export const ImageUploader = forwardRef<ImageUploaderHandle, Props>(function ImageUploader(
  { images, onChange, onBusy },
  ref,
) {
  const { session, guest, openLogin } = useIdentity()
  const config = useData<UploadLimits>('/attachments/config', !!session)
  const [attempts, setAttempts] = useState<Attempt[]>([]),
    [message, setMessage] = useState('')
  const currentImages = useRef(images),
    currentAttempts = useRef(attempts)
  useEffect(() => {
    currentImages.current = images
  }, [images])
  useEffect(() => {
    currentAttempts.current = attempts
    onBusy(attempts.length > 0)
  }, [attempts, onBusy])
  useEffect(
    () => () => {
      currentAttempts.current.forEach((a) => a.controller.abort())
    },
    [],
  )
  function update(key: string, change: Partial<Attempt>) {
    setAttempts((old) => old.map((a) => (a.key === key ? { ...a, ...change } : a)))
  }
  async function send(attempt: Attempt) {
    try {
      const image = await uploadImage(
        attempt.file,
        attempt.key,
        session!.csrf_token,
        (progress) => update(attempt.key, { progress }),
        attempt.controller.signal,
      )
      currentImages.current = [...currentImages.current, image]
      onChange(currentImages.current)
      setAttempts((old) => old.filter((a) => a.key !== attempt.key))
    } catch (e) {
      if (!attempt.controller.signal.aborted) update(attempt.key, { error: (e as Error).message })
    }
  }
  function add(files: File[]) {
    if (guest || !session) {
      openLogin()
      return
    }
    if (config.isPending) {
      setMessage('正在读取上传配置，请稍候再试。')
      return
    }
    if (!config.data?.is_available) {
      setMessage('图片存储未就绪，请先完成本地媒体配置。')
      return
    }
    if (
      currentImages.current.length + currentAttempts.current.length + files.length >
      config.data.max_images
    ) {
      setMessage(`每卡最多${config.data.max_images}张图片`)
      return
    }
    const valid = files.filter(
      (file) => file.size <= config.data!.max_bytes && config.data!.formats.includes(file.type),
    )
    setMessage(valid.length < files.length ? '部分文件类型不支持或超过大小限制，请检查。' : '')
    const next = valid.map((file) => ({
      file,
      key: crypto.randomUUID(),
      progress: 0,
      controller: new AbortController(),
    }))
    currentAttempts.current = [...currentAttempts.current, ...next]
    setAttempts(currentAttempts.current)
    next.forEach((a) => void send(a))
  }
  useImperativeHandle(ref, () => ({ addFiles: add }))
  function change(index: number, fields: Partial<Attachment>) {
    onChange(images.map((a, n) => (n === index ? { ...a, ...fields } : a)))
  }
  function move(index: number, delta: number) {
    const next = [...images]
    ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
    onChange(next)
  }
  return (
    <section
      className="image-uploader"
      tabIndex={0}
      aria-label="图片上传区域"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        add([...e.dataTransfer.files])
      }}
      onPaste={(e) => {
        const files = [...e.clipboardData.files]
        if (files.length) {
          e.preventDefault()
          add(files)
        }
      }}
    >
      <h3>图片材料</h3>
      <label>
        上传图片
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          onChange={(e) => {
            add([...(e.target.files || [])])
            e.target.value = ''
          }}
        />
      </label>
      <p className="muted">
        可选择、拖入或粘贴图片。
        {config.data
          ? `静态JPEG／PNG／WebP，每张最多${Math.round(config.data.max_bytes / 1024 / 1024)} MiB、${config.data.max_pixels / 1000000}百万像素、最长边${config.data.max_edge}，每卡${config.data.max_images}图。`
          : '正在读取上传限制…'}
      </p>
      {message && <p role="alert">{message}</p>}
      {config.error && <p role="alert">{config.error.message}</p>}
      {images.map((image, i) => (
        <div className="uploaded-image" key={image.id}>
          <PrivateImage attachment={image} />
          <label>
            图注 {i + 1}
            <input
              value={image.caption || ''}
              maxLength={2000}
              onChange={(e) => change(i, { caption: e.target.value })}
            />
          </label>
          <label>
            替代文本 {i + 1}
            <input
              value={image.alt_text || ''}
              maxLength={2000}
              onChange={(e) => change(i, { alt_text: e.target.value })}
            />
          </label>
          <label>
            图片作者 {i + 1}
            <input
              value={image.creator_name || ''}
              maxLength={200}
              onChange={(e) => change(i, { creator_name: e.target.value })}
            />
          </label>
          <div>
            <button type="button" disabled={i === 0} onClick={() => move(i, -1)}>
              上移图片
            </button>
            <button type="button" disabled={i === images.length - 1} onClick={() => move(i, 1)}>
              下移图片
            </button>
            <button type="button" onClick={() => onChange(images.filter((a) => a.id !== image.id))}>
              移除图片
            </button>
          </div>
        </div>
      ))}
      {attempts.map((attempt) => (
        <div className="upload-attempt" key={attempt.key}>
          <span>
            {attempt.file.name} · {attempt.error || `${attempt.progress}%（完成校验后可保存）`}
          </span>
          {attempt.error && (
            <button
              type="button"
              onClick={() => {
                const next = {
                  ...attempt,
                  error: undefined,
                  progress: 0,
                  controller: new AbortController(),
                }
                update(attempt.key, next)
                void send(next)
              }}
            >
              重试上传
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              attempt.controller.abort()
              setAttempts((old) => old.filter((a) => a.key !== attempt.key))
            }}
          >
            移除未完成项
          </button>
        </div>
      ))}
    </section>
  )
})
