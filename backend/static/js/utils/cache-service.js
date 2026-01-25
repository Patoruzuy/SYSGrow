/**
 * CacheService
 * ============================================================================
 * Prefix-based localStorage caching with TTL + wildcard clearing.
 *
 * Improvements:
 *  - wildcard patterns are safely converted into regex (escapes metacharacters)
 *  - quota exceeded detection is more cross-browser reliable
 *  - robust JSON parse handling
 */
(function () {
  'use strict';

  class CacheService {
    /**
     * @param {string} prefix
     * @param {number} ttl - ms
     */
    constructor(prefix = 'app', ttl = 5 * 60 * 1000) {
      this.prefix = prefix;
      this.ttl = ttl;
    }

    get(key) {
      const fullKey = this._getKey(key);
      try {
        const raw = localStorage.getItem(fullKey);
        if (!raw) return null;

        const cached = JSON.parse(raw);
        const ts = cached?.timestamp || 0;

        if (this._isExpired(ts)) {
          this.invalidate(key);
          return null;
        }

        return cached?.data ?? null;
      } catch (error) {
        // If the stored value is corrupted, remove it so we stop failing repeatedly.
        try { localStorage.removeItem(fullKey); } catch {}
        console.warn(`[CacheService] Failed to read ${key}:`, error);
        return null;
      }
    }

    set(key, data) {
      const fullKey = this._getKey(key);

      try {
        const payload = JSON.stringify({ data, timestamp: Date.now() });
        localStorage.setItem(fullKey, payload);
      } catch (error) {
        console.warn(`[CacheService] Failed to save ${key}:`, error);

        const quotaExceeded =
          error?.name === 'QuotaExceededError' ||
          error?.name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
          (error instanceof DOMException && (error.code === 22 || error.code === 1014));

        if (quotaExceeded) {
          // Best-effort recovery: clear a few oldest entries and try once more.
          this.clearOldest(8);
          try {
            const payload = JSON.stringify({ data, timestamp: Date.now() });
            localStorage.setItem(fullKey, payload);
          } catch (retryErr) {
            console.warn(`[CacheService] Retry failed to save ${key}:`, retryErr);
          }
        }
      }
    }

    has(key) {
      return this.get(key) !== null;
    }

    invalidate(key) {
      try {
        localStorage.removeItem(this._getKey(key));
      } catch (error) {
        console.warn(`[CacheService] Failed to invalidate ${key}:`, error);
      }
    }

    clear() {
      try {
        this._getAllKeys().forEach((k) => localStorage.removeItem(k));
      } catch (error) {
        console.warn('[CacheService] Failed to clear cache:', error);
      }
    }

    clearPattern(pattern) {
      try {
        const regex = this._wildcardToRegex(pattern);
        const keys = this._getAllKeys();

        for (const fullKey of keys) {
          const shortKey = fullKey.replace(`${this.prefix}_`, '');
          if (regex.test(shortKey)) localStorage.removeItem(fullKey);
        }
      } catch (error) {
        console.warn('[CacheService] Failed to clear pattern:', error);
      }
    }

    /**
     * Backward-compatible alias used by your dashboard modules.
     */
    clearByPattern(pattern) {
      const normalized = pattern.includes('*') ? pattern : `${pattern}*`;
      return this.clearPattern(normalized);
    }

    clearOldest(count = 5) {
      try {
        const keys = this._getAllKeys();

        const entries = keys.map((key) => {
          try {
            const item = JSON.parse(localStorage.getItem(key));
            return { key, timestamp: item?.timestamp || 0 };
          } catch {
            return { key, timestamp: 0 };
          }
        });

        entries.sort((a, b) => a.timestamp - b.timestamp);

        for (const entry of entries.slice(0, count)) {
          localStorage.removeItem(entry.key);
        }
      } catch (error) {
        console.warn('[CacheService] Failed to clear oldest:', error);
      }
    }

    getStats() {
      const keys = this._getAllKeys();
      let totalSize = 0;
      let expiredCount = 0;

      for (const key of keys) {
        try {
          const item = localStorage.getItem(key);
          totalSize += item?.length || 0;

          const cached = JSON.parse(item);
          if (this._isExpired(cached?.timestamp || 0)) expiredCount++;
        } catch {
          // ignore
        }
      }

      return {
        count: keys.length,
        expiredCount,
        sizeBytes: totalSize,
        sizeKB: (totalSize / 1024).toFixed(2),
        prefix: this.prefix,
        ttlMs: this.ttl,
      };
    }

    _getKey(key) {
      return `${this.prefix}_${key}`;
    }

    _getAllKeys() {
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(`${this.prefix}_`)) keys.push(key);
      }
      return keys;
    }

    _isExpired(timestamp) {
      return Date.now() - (timestamp || 0) > this.ttl;
    }

    /**
     * Convert wildcard pattern like:
     *   "system_health:*"
     * into a safe regex that matches the entire key.
     */
    _wildcardToRegex(pattern) {
      const escaped = String(pattern)
        .replace(/[.+?^${}()|[\]\\]/g, '\\$&') // escape regex meta except "*"
        .replace(/\*/g, '.*'); // wildcard expansion
      return new RegExp(`^${escaped}$`);
    }
  }

  window.CacheService = CacheService;
})();
