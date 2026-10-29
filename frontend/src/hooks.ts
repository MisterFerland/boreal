import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
export function useStoredState<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(`boreal.v1.${key}`)
      return saved ? (JSON.parse(saved) as T) : fallback
    } catch {
      return fallback
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(`boreal.v1.${key}`, JSON.stringify(value))
    } catch {
      /* Browser storage is optional; in-memory navigation remains available. */
    }
  }, [key, value])
  return [value, setValue] as const
}
export function useResource<T>(path: string | null, version = 0, poll = false) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision((value) => value + 1), [])
  useEffect(() => {
    if (!path) {
      setLoading(false)
      return
    }
    let alive = true
    const controller = new AbortController()
    const load = async () => {
      try {
        const result = await api<T>(path, { signal: controller.signal })
        if (alive) {
          setData(result)
          setError(null)
        }
      } catch (cause) {
        if (alive) setError(cause as Error)
      } finally {
        if (alive) setLoading(false)
      }
    }
    void load()
    const timer = poll ? window.setInterval(() => void load(), 5000) : undefined
    return () => {
      alive = false
      controller.abort()
      if (timer) window.clearInterval(timer)
    }
  }, [path, version, revision, poll])
  return { data, error, loading, refresh }
}
