type CacheRecord = {
  data: unknown;
  ts: number;
};

const cache = new Map<string, CacheRecord>();

export function setCache(key: string, data: unknown) {
  cache.set(key, { data, ts: Date.now() });
}

export function getCache<T>(key: string, ttlMs = 30_000): T | null {
  const item = cache.get(key);
  if (!item) {
    return null;
  }
  if (Date.now() - item.ts > ttlMs) {
    cache.delete(key);
    return null;
  }
  return item.data as T;
}
