class OperacionalLiveDashboard {
    constructor() {
        this.symbol = 'BTCUSDT';
        this.currentMarket = 'crypto';
        this.timeframe = '15m';
        this.chartEngine = null;
        this.chart = null;
        this.candleSeries = null;
        this.lastCandles = [];
        this.websocketEngine = window.WebSocketEngine ? new window.WebSocketEngine({ provider: 'binance' }) : null;
        this.marketDataEngine = window.MarketDataEngine ? new window.MarketDataEngine({ provider: 'binance', ttl: 6000 }) : null;
        this.statusTimer = null;
        this.tickTimer = null;
        this.statusController = null;
        this.assetsByMarket = {};
        this.streaming = true;
        this.voiceEnabled = false;
        this.lastVoiceMessage = '';
        this.init();
    }

    async init() {
        this.setupChart();
        this.bindEvents();
        await this.loadAssets();
        await this.loadCandles(true);
        await this.fetchStatus('initial');
        await this.fetchSignals();
        this.connectStreams();
    }

    bindEvents() {
        document.getElementById('opLiveMarketSelect')?.addEventListener('change', async (event) => {
            this.currentMarket = event.target.value;
            await this.loadAssets();
            this.reset(true);
        });
        document.getElementById('opLiveAssetSelect')?.addEventListener('change', (event) => {
            this.symbol = event.target.value;
            this.reset(true);
        });
        document.querySelectorAll('[data-op-live-tf]').forEach((button) => {
            button.addEventListener('click', (event) => {
                document.querySelectorAll('[data-op-live-tf]').forEach((item) => item.classList.remove('active'));
                event.currentTarget.classList.add('active');
                this.timeframe = event.currentTarget.dataset.opLiveTf;
                this.reset(true);
            });
        });
        document.getElementById('opLiveFitChart')?.addEventListener('click', () => this.chart?.timeScale().fitContent());
        document.getElementById('btnOpLiveSignals')?.addEventListener('click', () => {
            document.getElementById('op-live-signals')?.scrollIntoView({ behavior: 'smooth' });
        });
        document.getElementById('opVoiceToggle')?.addEventListener('click', () => this.toggleVoice());
        document.getElementById('opLiveVoiceToggle')?.addEventListener('click', () => this.toggleVoice());
        document.getElementById('opVoiceStop')?.addEventListener('click', () => speechSynthesis.cancel());
        window.addEventListener('resize', () => this.resizeChart());
    }

    setupChart() {
        this.chartEngine = new window.LiveChartEngine('opLiveChart', {
            minHeight: 620,
            watermark: {
                visible: true,
                text: 'Live Operacional Grafico',
                color: 'rgba(56, 189, 248, 0.12)',
                fontSize: 16,
                horzAlign: 'right',
                vertAlign: 'bottom',
            },
        }).init();
        this.chart = this.chartEngine?.chart;
        this.candleSeries = this.chartEngine?.candleSeries;
    }

    resizeChart() {
        this.chartEngine?.resize();
    }

    async loadAssets() {
        const response = await fetch(`/api/assets?market=${encodeURIComponent(this.currentMarket)}`);
        const data = await response.json();
        const marketSelect = document.getElementById('opLiveMarketSelect');
        const assetSelect = document.getElementById('opLiveAssetSelect');
        if (marketSelect && Array.isArray(data.markets)) {
            marketSelect.innerHTML = data.markets.map((market) => `<option value="${market.key}">${market.label}</option>`).join('');
            marketSelect.value = this.currentMarket;
        }
        if (assetSelect && Array.isArray(data.assets)) {
            assetSelect.innerHTML = data.assets.map((asset) => `<option value="${asset.symbol}">${asset.symbol} - ${asset.name}</option>`).join('');
            if (!data.assets.some((asset) => asset.symbol === this.symbol)) this.symbol = data.assets[0]?.symbol || 'BTCUSDT';
            assetSelect.value = this.symbol;
        }
    }

    async reset(fit = false) {
        this.statusController?.abort();
        clearTimeout(this.statusTimer);
        clearTimeout(this.tickTimer);
        this.websocketEngine?.close();
        this.chartEngine?.clearOverlays();
        this.setConnection('Atualizando');
        await this.loadCandles(fit);
        await this.fetchStatus('change');
        await this.fetchSignals();
        this.connectStreams();
    }

    async loadCandles(fit = false) {
        try {
            const response = await fetch(`/api/operacional/candles/${this.symbol}/${this.timeframe}?limit=260`);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'candles_unavailable');
            const candles = Array.isArray(data.candles) ? data.candles : [];
            this.chartEngine?.setData(candles, data.volumes || [], fit);
            this.lastCandles = this.chartEngine?.lastCandles || candles;
            const last = candles[candles.length - 1] || {};
            this.streaming = data.streaming ?? String(this.symbol).endsWith('USDT');
            this.setText('opLivePrice', this.formatPrice(last.close));
            this.setText('opLiveChartTitle', `${this.symbol} · ${String(data.source || '--').toUpperCase()} · ${this.timeframe}`);
            this.setText('opLiveDataSource', String(data.source || '--').toUpperCase());
            this.setText('opLiveMarketStatus', this.statusLabel(data.market_status));
            this.setConnection(this.streaming ? 'Grafico ativo' : 'REST / historico');
        } catch (error) {
            this.setConnection('Falha REST');
            this.pushMessages(['Nao foi possivel carregar candles operacionais.']);
        }
    }

    connectStreams() {
        this.websocketEngine?.close();
        clearTimeout(this.tickTimer);

        if (!this.streaming) {
            this.setConnection('REST / historico');
            console.log('[OpLive] Ativo sem streaming, usando REST.');
            this.scheduleStatus();
            return;
        }
        if (!String(this.symbol).endsWith('USDT')) {
            this.startTickPolling();
            console.log('[OpLive] Ativo nao-USDT, usando tick polling.');
            this.scheduleStatus();
            return;
        }
        if (!this.websocketEngine) {
            console.warn('[OpLive] WebSocketEngine nao disponivel, fallback REST.');
            this.scheduleStatus();
            return;
        }
        console.log(`[OpLive] Conectando WebSocket: ${this.symbol} ${this.timeframe}`);
        this.websocketEngine.connectKline({
            symbol: this.symbol,
            timeframe: this.timeframe,
            includeTrades: true,
            onState: (state) => this.setConnection(state),
            onKline: (kline) => {
                const candle = kline.candle;
                const volume = kline.volume;
                if (!this.chartEngine?.update(candle, volume)) return;
                this.lastCandles = this.chartEngine?.lastCandles || [...this.lastCandles.filter((item) => item.time !== candle.time), candle].slice(-260);
                this.setText('opLivePrice', this.formatPrice(candle.close));
                if (kline.isClosed) {
                    console.log('[OpLive] Candle fechado, re-analisando.');
                    this.fetchStatus('new_candle');
                    this.fetchSignals();
                }
            },
        });
        this.scheduleStatus();
    }

    startTickPolling() {
        clearTimeout(this.tickTimer);
        this.setConnection('Tick tempo real');
        const poll = async () => {
            try {
                const response = await fetch(`/api/market/tick/${encodeURIComponent(this.symbol)}?refresh=${Date.now()}`);
                const tick = await response.json();
                if (tick?.success) {
                    this.applyRealtimeTick(tick);
                    this.setConnection(`${String(tick.source || 'tick').toUpperCase()} tempo real`);
                } else {
                    this.setConnection('Tick indisponivel');
                    if (tick?.message) this.pushMessages([tick.message]);
                }
            } catch (error) {
                this.setConnection('Polling REST');
            } finally {
                this.tickTimer = setTimeout(poll, document.hidden ? 5000 : 1000);
            }
        };
        poll();
    }

    applyRealtimeTick(tick) {
        const price = Number(tick.last ?? tick.lastPrice ?? tick.bid ?? tick.ask);
        if (!Number.isFinite(price) || price <= 0) return;
        const time = Number(tick.time) > 0 ? Number(tick.time) : Math.floor(Date.now() / 1000);
        const candleTime = this.bucketTime(time, this.timeframe);
        const previous = (this.chartEngine?.lastCandles || this.lastCandles || []).slice(-1)[0];
        const sameCandle = previous && Number(previous.time) === candleTime;
        const candle = {
            time: candleTime,
            open: sameCandle ? Number(previous.open) : price,
            high: sameCandle ? Math.max(Number(previous.high), price) : price,
            low: sameCandle ? Math.min(Number(previous.low), price) : price,
            close: price,
            volume: Number(tick.volume ?? previous?.volume ?? 0) || 0,
        };
        const volume = {
            time: candle.time,
            value: Number(candle.volume) || 0,
            color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.45)' : 'rgba(239, 83, 80, 0.45)',
        };
        if (!this.chartEngine?.update(candle, volume)) return;
        this.lastCandles = this.chartEngine?.lastCandles || [...(this.lastCandles || []).filter((item) => item.time !== candle.time), candle].slice(-260);
        this.setText('opLivePrice', this.formatPrice(price));
        this.setText('opLiveDataSource', String(tick.source || '--').toUpperCase());
        this.setText('opLiveMarketStatus', this.statusLabel(tick.market_status || 'open'));
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

    scheduleStatus() {
        clearTimeout(this.statusTimer);
        this.statusTimer = setTimeout(() => this.fetchStatus('heartbeat'), 12000);
    }

    async fetchStatus(reason = 'heartbeat') {
        this.statusController?.abort();
        this.statusController = new AbortController();
        try {
            const response = await fetch(`/api/operacional-live/status/${this.symbol}/${this.timeframe}?reason=${encodeURIComponent(reason)}`, {
                signal: this.statusController.signal,
            });
            const status = await response.json();
            this.renderStatus(status);
        } catch (error) {
            if (error.name !== 'AbortError') this.pushMessages(['Falha temporaria na leitura operacional ao vivo.']);
        } finally {
            this.scheduleStatus();
        }
    }

    renderStatus(status) {
        if (!status?.success) {
            this.setText('opLiveStatus', 'AGUARDAR');
            this.setText('opLiveMainMessage', status?.messages?.[0] || 'Sem contexto operacional.');
            return;
        }
        this.setText('opLiveStatus', status.status || '--');
        this.setText('opLiveDirection', status.direction || '--');
        this.setText('opLiveScenario', status.scenario || '--');
        this.setText('opLiveConfidence', `${Math.round(Number(status.confidence || 0))}%`);
        this.setText('opLiveStrength', status.movement_strength || '--');
        this.setText('opLiveRiskReward', Number.isFinite(Number(status.risk_reward)) ? `1:${Number(status.risk_reward).toFixed(2)}` : '--');
        this.setText('opLiveAggressive', status.price_obligation?.status ? `${status.price_obligation.status} / ${status.price_obligation.kind}` : status.price_obligation?.kind || '--');
        this.setText('opLiveConservative', status.three_candle_pattern?.status ? `3C ${status.three_candle_pattern.status} / ${status.three_candle_pattern.score}` : status.fractal?.dominant_timeframe ? `${status.active_trigger?.active || '--'} / ${status.fractal.dominant_timeframe}` : status.active_trigger?.active || '--');
        this.setText('opLiveEntry', this.formatPrice(status.entry_aggressive));
        this.setText('opLiveStop', this.formatPrice(status.stop_loss));
        this.setText('opLiveTake1', this.formatPrice(status.take_profit_1));
        this.setText('opLiveTake2', this.formatPrice(status.take_profit_2));
        this.setText('opLiveReason', status.three_candle_pattern?.explanation ? `${status.three_candle_pattern.explanation} ${status.reason || ''}` : status.behavior?.intention ? `${status.behavior.intention} ${status.reason || ''}` : status.reason || '--');
        if (Array.isArray(status.operation_blockers) && status.operation_blockers.length) {
            this.setText('opLiveReason', status.operation_blockers.slice(0, 2).join(' / '));
        }
        this.setText('opLiveMarketStatus', status.fractal?.conflict ? 'CONFLITO FRACTAL' : status.market_status || status.market_status_raw || '--');
        document.getElementById('opLiveStatusCard').dataset.state = status.state || 'AGUARDAR';
        this.pushMessages(status.messages || []);
        const markers = window.VisualAIOverlays?.buildOperationalMarkers(this.lastCandles, status) || [];
        this.chartEngine?.applyMarkers(markers);
        this.renderPriceLines(status.chart_marks?.price_lines || []);
        this.speak(status.messages?.[0] || status.reason || '');
    }

    async fetchSignals() {
        const response = await fetch(`/api/operacional-live/signals/${this.symbol}/${this.timeframe}`);
        const data = await response.json();
        this.renderSignals(data.signals || []);
    }

    renderSignals(signals) {
        this.setText('opLiveSignalsCount', signals.length);
        const grid = document.getElementById('opLiveSignalsGrid');
        if (!grid) return;
        if (!signals.length) {
            grid.innerHTML = '<div class="live-empty-signal">Aguardando contexto operacional.</div>';
            return;
        }
        grid.innerHTML = signals.slice().reverse().map((signal) => `
            <article class="live-signal-card ${String(signal.direction || '').toLowerCase()}">
                <div class="live-signal-head">
                    <div><h4>${this.escape(signal.symbol)} · ${this.escape(signal.timeframe)}</h4><small>${this.formatDate(signal.timestamp)}</small></div>
                    <span class="live-signal-direction">${this.escape(signal.direction)}</span>
                </div>
                <div class="live-signal-metrics">
                    <div><span>Conf.</span><strong>${Math.round(Number(signal.confidence || 0))}%</strong></div>
                    <div><span>Status</span><strong>${this.escape(signal.status)}</strong></div>
                    <div><span>R/R</span><strong>${signal.risk_reward ? `1:${Number(signal.risk_reward).toFixed(2)}` : '--'}</strong></div>
                    <div><span>Bloqueio</span><strong>${signal.blocked ? 'SIM' : 'NAO'}</strong></div>
                </div>
                <div class="live-signal-levels">
                    <div><span>Entrada</span><strong>${this.formatPrice(signal.entry)}</strong></div>
                    <div><span>Stop</span><strong>${this.formatPrice(signal.stop_loss)}</strong></div>
                    <div><span>Alvo</span><strong>${this.formatPrice(signal.take_profit_1)}</strong></div>
                </div>
                <p class="live-signal-reason">${this.escape(signal.blocked ? (signal.operation_blockers || []).join(' / ') : signal.reason || signal.explanation || '--')}</p>
                <p class="live-signal-reason">${this.escape(signal.three_candle_pattern?.status ? `3 candles: ${signal.three_candle_pattern.status} / ${signal.three_candle_pattern.score}` : '')}</p>
            </article>
        `).join('');
    }

    renderPriceLines(lines) {
        this.chartEngine?.applyLevels((Array.isArray(lines) ? lines : []).map((line) => ({
            label: line.label || line.type,
            price: line.price,
            color: line.color || '#D4AF37',
            lineWidth: line.type === 'entry' ? 2 : 1,
        })));
    }

    pushMessages(messages) {
        const feed = document.getElementById('opLiveMessageFeed');
        if (!feed) return;
        feed.innerHTML = (messages.length ? messages : ['Aguardando leitura operacional.']).map((message) => (
            `<div class="live-message-row"><i class="fas fa-wave-square"></i><span>${this.escape(message)}</span></div>`
        )).join('');
    }

    toggleVoice() {
        this.voiceEnabled = !this.voiceEnabled;
        this.setText('opVoiceStatus', this.voiceEnabled ? 'LIGADA' : 'DESLIGADA');
        document.getElementById('opLiveVoiceToggle')?.querySelector('i')?.classList.toggle('fa-volume-up', this.voiceEnabled);
    }

    speak(message) {
        if (!this.voiceEnabled || !message || message === this.lastVoiceMessage || !('speechSynthesis' in window)) return;
        this.lastVoiceMessage = message;
        this.setText('opVoiceLastMessage', message);
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.lang = 'pt-BR';
        utterance.volume = Number(document.getElementById('opVoiceVolume')?.value || 0.85);
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
    }

    setConnection(value) {
        this.setText('opLiveConnection', value);
        this.updateRealtimeBadge(value);
    }

    updateRealtimeBadge(rawState) {
        const status = this.realtimeBadgeStatus(rawState);
        let badge = document.getElementById('realtimeStatusBadge');
        if (!badge) {
            badge = document.createElement('div');
            badge.id = 'realtimeStatusBadge';
            badge.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:9999;padding:6px 10px;border-radius:999px;font:600 11px Inter,Arial,sans-serif;letter-spacing:0;background:rgba(3,7,18,.86);border:1px solid rgba(148,163,184,.24);box-shadow:0 8px 24px rgba(0,0,0,.22);pointer-events:none;';
            document.body.appendChild(badge);
        }
        badge.textContent = status.label;
        badge.style.color = status.color;
        badge.style.borderColor = status.border;
    }

    realtimeBadgeStatus(rawState) {
        const state = String(rawState || '').toLowerCase();
        const wsActive = this.websocketEngine?.socket?.readyState === WebSocket.OPEN;
        if (state.includes('rest') || state.includes('tick') || state.includes('polling') || state.includes('historico') || state.includes('indisponivel')) {
            return { label: 'Fallback REST/Tick', color: '#facc15', border: 'rgba(250,204,21,.36)' };
        }
        if (state.includes('reconect') || state.includes('falh') || state.includes('atualizando') || state.includes('carregando')) {
            return { label: 'Reconectando...', color: '#fb923c', border: 'rgba(251,146,60,.38)' };
        }
        if (wsActive || state.includes('websocket') || state.includes('bybit')) {
            return { label: 'Realtime ativo', color: '#22c55e', border: 'rgba(34,197,94,.38)' };
        }
        return { label: 'Reconectando...', color: '#fb923c', border: 'rgba(251,146,60,.38)' };
    }

    setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value == null || value === '' ? '--' : value;
    }

    statusLabel(status) {
        const labels = { open: 'Aberto', closed: 'Fechado', fallback: 'Fallback', no_data: 'Sem dados', unknown: 'Indefinido' };
        return labels[status] || status || '--';
    }

    formatPrice(value) {
        const num = Number(value);
        if (!Number.isFinite(num) || num === 0) return '--';
        return num >= 100 ? num.toFixed(2) : num.toFixed(5);
    }

    formatDate(value) {
        if (!value) return '--';
        return new Date(value).toLocaleString('pt-BR');
    }

    escape(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}

document.addEventListener('DOMContentLoaded', () => new OperacionalLiveDashboard());
