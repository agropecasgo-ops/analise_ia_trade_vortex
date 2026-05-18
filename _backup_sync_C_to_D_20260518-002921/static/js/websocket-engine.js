(function () {
    class WebSocketEngine {
        constructor(options = {}) {
            this.provider = options.provider || 'binance';
            this.fallbackProvider = options.fallbackProvider || 'binance';
            this.socket = null;
            this.currentUrl = '';
            this.currentSubscription = '';
            this.generation = 0;
            this.reconnectTimer = null;
            this.heartbeatTimer = null;
            this.activeCandle = null;
            this.activeVolume = null;
            this.reconnectDelay = options.reconnectDelay || 2500;
            this.maxReconnectDelay = options.maxReconnectDelay || 20000;
        }

        connectKline(options) {
            if (this.provider === 'bybit') {
                this.connectBybitKline({
                    ...options,
                    onFallback: () => this.connectBinanceKline({ ...options, includeTrades: options.includeTrades ?? false }),
                });
                return;
            }
            this.connectBinanceKline(options);
        }

        connectBinanceKline({ symbol, timeframe, includeTrades = false, onKline, onTrade, onState }) {
            const base = `${String(symbol).toLowerCase()}@kline_${timeframe}`;
            const streams = includeTrades ? `${base}/${String(symbol).toLowerCase()}@aggTrade` : base;
            const url = includeTrades
                ? `wss://stream.binance.com:9443/stream?streams=${streams}`
                : `wss://stream.binance.com:9443/ws/${base}`;
            if (this.currentUrl === url && this.socket && this.socket.readyState <= 1) return;
            this.close();
            this.currentUrl = url;
            const generation = ++this.generation;
            this.socket = new WebSocket(url);
            this.socket.onopen = () => {
                if (generation !== this.generation) return;
                this.reconnectDelay = 2500;
                onState?.('WebSocket');
            };
            this.socket.onerror = () => {
                if (generation === this.generation) onState?.('WebSocket falhou');
            };
            this.socket.onclose = () => {
                if (generation !== this.generation) return;
                onState?.('Reconectando');
                this.reconnectTimer = setTimeout(() => {
                    if (!document.hidden && generation === this.generation) {
                        this.connectBinanceKline({ symbol, timeframe, includeTrades, onKline, onTrade, onState });
                    }
                }, this.reconnectDelay);
                this.reconnectDelay = Math.min(this.reconnectDelay * 1.6, this.maxReconnectDelay);
            };
            this.socket.onmessage = (event) => {
                if (generation !== this.generation) return;
                const payload = JSON.parse(event.data);
                const stream = payload.stream || '';
                const data = payload.data || payload;
                if (stream.includes('@aggTrade') || data.e === 'aggTrade') {
                    const realtimeKline = includeTrades ? this.klineFromTrade(data, timeframe) : null;
                    if (realtimeKline) onKline?.(realtimeKline);
                    onTrade?.(data);
                    return;
                }
                const kline = data.k;
                if (kline) onKline?.(this.rememberKline(this.normalizeKline(kline, true)));
            };
        }

        connectBybitKline({ symbol, timeframe, onKline, onState, onFallback }) {
            const interval = this.bybitInterval(timeframe);
            const topic = `kline.${interval}.${String(symbol).toUpperCase()}`;
            const url = 'wss://stream.bybit.com/v5/public/spot';
            if (this.currentUrl === url && this.currentSubscription === topic && this.socket && this.socket.readyState <= 1) return;
            this.close();
            this.currentUrl = url;
            this.currentSubscription = topic;
            const generation = ++this.generation;
            this.socket = new WebSocket(url);
            this.socket.onopen = () => {
                if (generation !== this.generation) return;
                this.reconnectDelay = 2500;
                this.socket.send(JSON.stringify({ op: 'subscribe', args: [topic] }));
                this.startHeartbeat(() => this.socket?.send(JSON.stringify({ op: 'ping' })));
                onState?.('Bybit WS');
            };
            this.socket.onerror = () => {
                if (generation !== this.generation) return;
                onState?.('Bybit falhou');
                this.close();
                onFallback?.();
            };
            this.socket.onclose = () => {
                if (generation !== this.generation) return;
                onState?.('Reconectando');
                this.reconnectTimer = setTimeout(() => {
                    if (!document.hidden && generation === this.generation) {
                        this.connectBybitKline({ symbol, timeframe, onKline, onState, onFallback });
                    }
                }, this.reconnectDelay);
                this.reconnectDelay = Math.min(this.reconnectDelay * 1.6, this.maxReconnectDelay);
            };
            this.socket.onmessage = (event) => {
                if (generation !== this.generation) return;
                const payload = JSON.parse(event.data);
                if (payload.op === 'pong' || payload.ret_msg === 'pong') return;
                if (payload.op === 'subscribe' || payload.success) return;
                const item = Array.isArray(payload.data) ? payload.data[0] : payload.data;
                if (!item) return;
                onKline?.(this.rememberKline(this.normalizeKline({
                    t: Number(item.start),
                    o: item.open,
                    h: item.high,
                    l: item.low,
                    c: item.close,
                    v: item.volume,
                    x: Boolean(item.confirm),
                }, true)));
            };
        }

        normalizeKline(kline, official = false) {
            const time = this.normalizeTime(kline?.t ?? kline?.time);
            const candle = {
                time,
                open: Number(kline?.o ?? kline?.open),
                high: Number(kline?.h ?? kline?.high),
                low: Number(kline?.l ?? kline?.low),
                close: Number(kline?.c ?? kline?.close),
                volume: Number(kline?.v ?? kline?.volume ?? 0) || 0,
                official,
                closed: Boolean(kline?.x),
            };
            const volume = {
                time,
                value: candle.volume,
                color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.45)' : 'rgba(239, 83, 80, 0.45)',
            };
            return {
                ...kline,
                t: time * 1000,
                o: candle.open,
                h: candle.high,
                l: candle.low,
                c: candle.close,
                v: volume.value,
                x: Boolean(kline?.x),
                candle,
                volume,
                isClosed: Boolean(kline?.x),
            };
        }

        rememberKline(kline) {
            this.activeCandle = kline?.candle || null;
            this.activeVolume = kline?.volume || null;
            return kline;
        }

        klineFromTrade(trade, timeframe) {
            const price = Number(trade?.p ?? trade?.price);
            if (!Number.isFinite(price) || price <= 0) return null;
            const quantity = Number(trade?.q ?? trade?.quantity ?? 0) || 0;
            const tradeTime = this.normalizeTime(trade?.T ?? trade?.E ?? trade?.time);
            const time = this.bucketTime(tradeTime, timeframe);
            const previous = this.activeCandle;
            const sameCandle = previous && Number(previous.time) === time;
            if (previous && !sameCandle && !previous.closed) return null;
            const baseOpen = sameCandle ? Number(previous.open) : Number(previous?.close || price);
            const previousVolume = sameCandle ? Number(previous.volume || this.activeVolume?.value || 0) : 0;
            const candle = {
                time,
                open: baseOpen,
                high: sameCandle ? Math.max(Number(previous.high), price) : Math.max(baseOpen, price),
                low: sameCandle ? Math.min(Number(previous.low), price) : Math.min(baseOpen, price),
                close: price,
                volume: previousVolume + quantity,
                official: false,
                closed: false,
            };
            const volume = {
                time,
                value: candle.volume,
                color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.45)' : 'rgba(239, 83, 80, 0.45)',
            };
            const kline = {
                t: time * 1000,
                o: candle.open,
                h: candle.high,
                l: candle.low,
                c: candle.close,
                v: volume.value,
                x: false,
                candle,
                volume,
                isClosed: false,
                fromTrade: true,
            };
            this.activeCandle = candle;
            this.activeVolume = volume;
            return kline;
        }

        normalizeTime(value) {
            const time = Number(value);
            if (!Number.isFinite(time) || time <= 0) return Math.floor(Date.now() / 1000);
            return time > 9999999999 ? Math.floor(time / 1000) : Math.floor(time);
        }

        bucketTime(timestamp, timeframe) {
            const seconds = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400,
                '1w': 604800,
            }[timeframe] || 60;
            return Math.floor(Number(timestamp) / seconds) * seconds;
        }

        bybitInterval(timeframe) {
            return {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '1h': '60',
                '4h': '240',
                '1d': 'D',
                '1w': 'W',
            }[timeframe] || '15';
        }

        close() {
            clearTimeout(this.reconnectTimer);
            clearInterval(this.heartbeatTimer);
            this.generation += 1;
            this.activeCandle = null;
            this.activeVolume = null;
            if (this.socket) {
                this.socket.onclose = null;
                this.socket.close();
                this.socket = null;
            }
            this.currentUrl = '';
            this.currentSubscription = '';
        }

        startHeartbeat(sendPing) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = setInterval(() => {
                if (this.socket?.readyState === WebSocket.OPEN) {
                    try {
                        sendPing();
                    } catch (error) {
                        this.socket.close();
                    }
                }
            }, 20000);
        }
    }

    window.WebSocketEngine = WebSocketEngine;
})();
