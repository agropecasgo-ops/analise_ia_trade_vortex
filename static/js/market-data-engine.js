(function () {
    class MarketDataEngine {
        constructor(options = {}) {
            this.provider = options.provider || 'binance';
            this.fallbackProvider = options.fallbackProvider || 'binance';
            this.cache = new Map();
            this.ttl = options.ttl || 8000;
            this.maxEntries = options.maxEntries || 80;
        }

        async candles(symbol, timeframe, limit = 240, signal, force = false) {
            const operationalMode = this.operationalMode();
            const key = `candles:${this.provider}:${symbol}:${timeframe}:${limit}:${operationalMode}`;
            if (!force) {
                const cached = this.get(key);
                if (cached) return cached;
            }
            const response = await fetch(`/api/candles/${encodeURIComponent(symbol)}/${encodeURIComponent(timeframe)}?limit=${limit}&operationalMode=${encodeURIComponent(operationalMode)}`, { signal });
            const data = await response.json();
            if (data?.success) this.set(key, data);
            return data;
        }

        async analysis(symbol, timeframe, signal, force = false) {
            const operationalMode = this.operationalMode();
            const key = `analysis:${this.provider}:${symbol}:${timeframe}:${operationalMode}`;
            if (!force) {
                const cached = this.get(key);
                if (cached) return cached;
            }
            const suffix = `?operationalMode=${encodeURIComponent(operationalMode)}${force ? `&refresh=${Date.now()}` : ''}`;
            const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/${encodeURIComponent(timeframe)}${suffix}`, { signal });
            const data = await response.json();
            if (data?.success) this.set(key, data);
            return data;
        }

        async tick(symbol, signal, force = false) {
            const key = `tick:${this.provider}:${symbol}`;
            if (!force) {
                const cached = this.get(key);
                if (cached) return cached;
            }
            const response = await fetch(`/api/market/tick/${encodeURIComponent(symbol)}`, { signal });
            const data = await response.json();
            if (data?.success) this.set(key, data, Math.min(this.ttl, 1200));
            return data;
        }

        get(key) {
            const record = this.cache.get(key);
            if (!record || Date.now() - record.time > (record.ttl || this.ttl)) {
                this.cache.delete(key);
                return null;
            }
            return record.data;
        }

        set(key, data, ttl = this.ttl) {
            this.cache.set(key, { time: Date.now(), ttl, data });
            while (this.cache.size > this.maxEntries) {
                this.cache.delete(this.cache.keys().next().value);
            }
        }

        operationalMode() {
            return window.FinanceOperationalMode?.get?.() || 'moderado';
        }

        invalidate(prefix = '') {
            [...this.cache.keys()].forEach((key) => {
                if (!prefix || key.includes(prefix)) this.cache.delete(key);
            });
        }
    }

    window.MarketDataEngine = MarketDataEngine;
})();
