import { useEffect, useRef } from 'react'
import { useBlocker } from 'react-router-dom'

export function useUnsaved(dirty: boolean) {
  const saved = useRef(false)
  const blocker = useBlocker(() => dirty && !saved.current)
  useEffect(() => {
    if (blocker.state === 'blocked') {
      if (window.confirm('内容尚未保存，确定离开？')) blocker.proceed()
      else blocker.reset()
    }
  }, [blocker])
  useEffect(() => {
    function unload(e: BeforeUnloadEvent) {
      if (dirty && !saved.current) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', unload)
    return () => window.removeEventListener('beforeunload', unload)
  }, [dirty])
  return () => {
    saved.current = true
  }
}
