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
                    onTrade?.(data);
                    return;
                }
                const kline = data.k;
                if (kline) onKline?.(kline);
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
                onKline?.({
                    t: Number(item.start),
                    o: item.open,
                    h: item.high,
                    l: item.low,
                    c: item.close,
                    v: item.volume,
                    x: Boolean(item.confirm),
                });
            };
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
