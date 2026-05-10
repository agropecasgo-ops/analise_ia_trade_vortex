class LiveTradingDashboard {
    constructor() {
        this.symbol = 'BTCUSDT';
        this.currentMarket = 'crypto';
        this.timeframe = '15m';
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.lastCandles = [];
        this.priceLines = [];
        this.socket = null;
        this.statusController = null;
        this.statusTimer = null;
        this.candlePollTimer = null;
        this.countdownTimer = null;
        this.lastCandleTime = 0;
        this.lastAnalysisPrice = 0;
        this.lastAnalysisVolume = 0;
        this.lastAlertSignature = '';
        this.lastSignalAlertSignature = '';
        this.lastVoiceState = '';
        this.soundEnabled = false;
        this.supportResistance = {};
        this.streaming = true;
        this.timeframeSeconds = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400 };
        this.init();
    }

    async init() {
        this.setupChart();
        this.bindEvents();
        window.financeVoiceAssistant?.bindControls('voice');
        await this.loadAssets();
        await this.loadInitialCandles(true);
        this.fetchLiveStatus('initial');
        this.fetchSignals();
        this.connectStreams();
        this.startCountdown();
    }

    bindEvents() {
        document.getElementById('liveMarketSelect')?.addEventListener('change', async (event) => {
            this.currentMarket = event.target.value;
            await this.loadAssets();
            this.resetLive(true);
        });
        document.getElementById('liveAssetSelect')?.addEventListener('change', (event) => {
            this.symbol = event.target.value;
            this.resetLive(true);
        });
        document.querySelectorAll('[data-live-tf]').forEach((button) => {
            button.addEventListener('click', (event) => {
                document.querySelectorAll('[data-live-tf]').forEach((item) => item.classList.remove('active'));
                event.currentTarget.classList.add('active');
                this.timeframe = event.currentTarget.dataset.liveTf;
                this.resetLive(true);
            });
        });
        document.getElementById('liveFitChart')?.addEventListener('click', () => this.chart?.timeScale().fitContent());
        document.getElementById('liveSoundToggle')?.addEventListener('click', () => this.toggleSound());
        document.getElementById('btnLiveSignals')?.addEventListener('click', () => {
            document.getElementById('signals')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        window.addEventListener('resize', () => this.resizeChart());
    }

    async loadAssets() {
        try {
            const response = await fetch(`/api/assets?market=${encodeURIComponent(this.currentMarket)}`);
            const data = await response.json();
            const select = document.getElementById('liveAssetSelect');
            const marketSelect = document.getElementById('liveMarketSelect');
            if (!data.success || !select) return;
            if (marketSelect && Array.isArray(data.markets)) {
                marketSelect.innerHTML = data.markets.map((market) => `<option value="${market.key}">${market.label}</option>`).join('');
                marketSelect.value = this.currentMarket;
            }
            select.innerHTML = data.assets.map((asset) => `<option value="${asset.symbol}">${asset.symbol} - ${asset.name}</option>`).join('');
            if (!data.assets.some((asset) => asset.symbol === this.symbol)) {
                this.symbol = data.assets[0]?.symbol || 'BTCUSDT';
            }
            select.value = this.symbol;
        } catch (error) {
            console.warn('Assets indisponiveis', error);
        }
    }

    setupChart() {
        const container = document.getElementById('liveChart');
        if (!container) return;
        container.innerHTML = '';
        this.chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: Math.max(container.clientHeight, 620),
            layout: {
                background: { type: 'solid', color: '#05070d' },
                textColor: '#F8FAFC',
                fontFamily: 'Inter, Arial, sans-serif',
            },
            grid: {
                horzLines: { color: 'rgba(56, 189, 248, 0.08)' },
                vertLines: { color: 'rgba(255, 255, 255, 0.035)' },
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: {
                borderColor: 'rgba(56, 189, 248, 0.18)',
                scaleMargins: { top: 0.08, bottom: 0.24 },
            },
            timeScale: {
                borderColor: 'rgba(56, 189, 248, 0.18)',
                timeVisible: true,
                secondsVisible: false,
            },
        });
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#22C55E',
            downColor: '#EF4444',
            borderUpColor: '#22C55E',
            borderDownColor: '#EF4444',
            wickUpColor: '#22C55E',
            wickDownColor: '#EF4444',
        });
        this.volumeSeries = this.chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: '',
            scaleMargins: { top: 0.82, bottom: 0 },
        });
    }

    resizeChart() {
        const container = document.getElementById('liveChart');
        if (!container || !this.chart) return;
        this.chart.applyOptions({ width: container.clientWidth, height: Math.max(container.clientHeight, 620) });
    }

    async resetLive(fit = false) {
        this.statusController?.abort();
        clearInterval(this.candlePollTimer);
        if (this.socket) {
            this.socket.onclose = null;
            this.socket.close();
            this.socket = null;
        }
        this.clearPriceLines();
        this.setConnection('Atualizando');
        await this.loadInitialCandles(fit);
        this.fetchLiveStatus('change');
        this.connectStreams();
    }

    async loadInitialCandles(fit = false) {
        try {
            this.setConnection('Carregando');
            const response = await fetch(`/api/candles/${this.symbol}/${this.timeframe}?limit=240`);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'candles_unavailable');
            const candles = Array.isArray(data.candles) ? data.candles : [];
            const volumes = Array.isArray(data.volumes) ? data.volumes : [];
            this.lastCandles = candles;
            this.candleSeries.setData(candles);
            this.volumeSeries.setData(volumes);
            const last = candles[candles.length - 1] || {};
            this.streaming = data.streaming ?? String(this.symbol).endsWith('USDT');
            this.lastCandleTime = Number(last.time || 0);
            this.lastAnalysisPrice = Number(last.close || 0);
            this.setText('livePrice', this.formatPrice(last.close || data.ticker?.lastPrice || 0));
            this.setText('liveChartTitle', `${this.symbol} · ${String(data.source || '--').toUpperCase()} · ${this.timeframe}`);
            this.setText('liveDataSource', String(data.source || '--').toUpperCase());
            this.setText('liveMarketStatus', this.getMarketStatusText(data.market_status));
            if (data.market_message) this.pushMessage(data.market_message);
            if (fit) this.chart.timeScale().fitContent();
            this.setConnection(this.streaming ? 'Grafico ativo' : 'REST / historico');
        } catch (error) {
            this.setConnection('REST falhou');
            this.pushMessage('Nao foi possivel carregar historico. Tentando manter a tela ativa.');
        }
    }

    connectStreams() {
        clearInterval(this.candlePollTimer);
        if (!this.streaming || !String(this.symbol).endsWith('USDT')) {
            this.setConnection('REST / historico');
            this.candlePollTimer = setInterval(() => this.loadInitialCandles(false), 60000);
            return;
        }
        const stream = `${this.symbol.toLowerCase()}@kline_${this.timeframe}`;
        const url = `wss://stream.binance.com:9443/ws/${stream}`;
        this.socket = new WebSocket(url);
        this.socket.onopen = () => this.setConnection('Tempo real');
        this.socket.onerror = () => this.setConnection('WebSocket falhou');
        this.socket.onclose = () => {
            this.setConnection('Reconectando');
            setTimeout(() => {
                if (!document.hidden) this.connectStreams();
            }, 2500);
        };
        this.socket.onmessage = (event) => this.handleKline(JSON.parse(event.data));
    }

    handleKline(payload) {
        const kline = payload.k;
        if (!kline) return;
        const candle = {
            time: Math.floor(kline.t / 1000),
            open: Number(kline.o),
            high: Number(kline.h),
            low: Number(kline.l),
            close: Number(kline.c),
        };
        const volume = {
            time: candle.time,
            value: Number(kline.v),
            color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.45)' : 'rgba(239, 83, 80, 0.45)',
        };
        this.candleSeries.update(candle);
        this.lastCandles = [...this.lastCandles.filter((item) => item.time !== candle.time), candle].slice(-260);
        this.volumeSeries.update(volume);
        this.setText('livePrice', this.formatPrice(candle.close));
        this.lastCandleTime = candle.time;

        const priceMove = this.lastAnalysisPrice ? Math.abs(candle.close - this.lastAnalysisPrice) / this.lastAnalysisPrice : 0;
        const volumeMove = this.lastAnalysisVolume ? Number(kline.v) / Math.max(this.lastAnalysisVolume, 0.00000001) : 1;
        const srBroken = this.isSupportResistanceBroken(candle.close);
        if (kline.x || priceMove >= 0.004 || volumeMove >= 1.8 || srBroken) {
            this.lastAnalysisPrice = candle.close;
            this.lastAnalysisVolume = Number(kline.v);
            this.fetchLiveStatus(kline.x ? 'new_candle' : srBroken ? 'support_resistance_break' : 'strong_change');
        }
    }

    fetchLiveStatus(reason) {
        this.statusController?.abort();
        this.statusController = new AbortController();
        clearTimeout(this.statusTimer);
        this.setStatusLoading(true);
        fetch(`/api/live/status/${this.symbol}/${this.timeframe}?reason=${encodeURIComponent(reason)}`, {
            signal: this.statusController.signal,
        })
            .then((response) => response.json())
            .then((data) => this.updateStatusPanel(data))
            .catch((error) => {
                if (error.name !== 'AbortError') {
                    this.pushMessage('IA recalculando em background. O grafico continua ativo.');
                }
            })
            .finally(() => this.setStatusLoading(false));
        this.statusTimer = setTimeout(() => this.fetchLiveStatus('heartbeat'), 20000);
    }

    updateStatusPanel(data) {
        if (!data) return;
        const state = data.state || 'ANALYZING';
        this.setText('liveOperationalStatus', data.status || 'ANALISANDO');
        this.setText('liveMainMessage', data.message || 'Analisando estrutura do mercado...');
        this.setText('liveScore', Number.isFinite(Number(data.confluence_score)) ? `${data.confluence_score}/100` : '--');
        this.setText('liveConfidence', Number.isFinite(Number(data.confidence)) ? `${data.confidence}%` : '--');
        this.setText('liveDirection', data.probable_direction || '--');
        this.setText('liveTrendStrength', Number.isFinite(Number(data.trend_strength)) ? `${data.trend_strength}%` : '--');
        this.setText('liveVolumeStrength', Number.isFinite(Number(data.volume_strength)) ? `${data.volume_strength}%` : '--');
        this.setText('liveRiskReward', Number.isFinite(Number(data.risk_reward)) ? `1:${Number(data.risk_reward).toFixed(2)}` : '--');
        this.setText('liveAggressiveEntry', this.formatPrice(data.entry_aggressive));
        this.setText('liveConservativeEntry', this.formatPrice(data.entry_conservative));
        this.setText('liveStopLoss', this.formatPrice(data.stop_loss));
        this.setText('liveTakeProfit', this.formatPrice(data.take_profit));
        this.setText('liveReason', data.reason || '--');
        this.setText('liveMarketStatus', this.getMarketStatusText(data.market_data_status || data.market_status));
        this.setText('liveDataSource', String(data.source || '--').toUpperCase());
        if (data.market_message) this.pushMessage(data.market_message);
        this.renderMessages(data.messages || []);
        this.renderInvalidations(data.invalidations || []);
        this.supportResistance = data.support_resistance || {};
        this.renderPriceLines(data);
        const markers = window.VisualAIOverlays?.buildCompleteMarkers(this.lastCandles, {
            signal_cards: { active: data.probable_direction === 'BUY' ? 'buy' : data.probable_direction === 'SELL' ? 'sell' : 'wait', label: data.status },
            technical_reader: data.technical || {},
            smc: data.smc || {},
            volume_analysis: data.volume || {},
            tape_reading: data.tape_reading || {},
        }) || [];
        window.VisualAIOverlays?.set(this.candleSeries, [], markers);
        this.applyStateVisual(state);
        this.handleAlerts(data.alerts || [], data.status || state);
        this.handleVoiceStatus(data);
        if (data.signal_event) this.renderSignalEvent(data.signal_event);
        this.fetchSignals();
    }

    handleVoiceStatus(data) {
        const state = data?.state || '';
        if (!state || state === this.lastVoiceState) return;
        this.lastVoiceState = state;
        window.financeVoiceAssistant?.speakLiveStatus(data);
    }

    fetchSignals() {
        fetch(`/api/live/signals?symbol=${encodeURIComponent(this.symbol)}&timeframe=${encodeURIComponent(this.timeframe)}`)
            .then((response) => response.json())
            .then((data) => {
                if (!data?.success) return;
                this.renderSignals(data.active || []);
                this.renderSignalEvent(data.signal);
                this.setText('liveSignalsCount', data.stats?.active_count ?? 0);
                this.setText('liveSignalsBadge', `${data.stats?.active_count ?? 0} oportunidades em tempo real`);
            })
            .catch(() => {});
    }

    renderSignalEvent(signal) {
        if (!signal || signal.status === 'waiting_confirmation') return;
        const signature = `${signal.id}:${signal.status}:${signal.partial_result || ''}`;
        if (signature === this.lastSignalAlertSignature) return;
        this.lastSignalAlertSignature = signature;
        if (['active', 'confirmed', 'invalidated', 'tp1_hit', 'tp2_hit', 'tp3_hit', 'stopped'].includes(signal.status)) {
            this.showToast(`Sinal IA ${signal.symbol}: ${this.signalStatusText(signal.status)}`, signal.status.includes('invalid') || signal.status === 'stopped' ? 'error' : 'success');
            if (this.soundEnabled) this.playAlertSound(signal.alerts || []);
            window.financeVoiceAssistant?.speakSignal(signal);
        }
    }

    renderSignals(signals) {
        const grid = document.getElementById('liveSignalsGrid');
        if (!grid) return;
        if (!signals.length) {
            grid.innerHTML = '<div class="live-empty-signal">Aguardando confluencia forte da IA...</div>';
            return;
        }
        grid.innerHTML = signals.map((signal) => this.signalCard(signal)).join('');
    }

    signalCard(signal) {
        const sideClass = String(signal.direction || '').toLowerCase();
        return `
            <article class="live-signal-card ${sideClass}">
                <div class="live-signal-head">
                    <div>
                        <h4>${signal.symbol || signal.asset} · ${signal.timeframe}</h4>
                        <small>${signal.market_label || signal.market || '--'}</small>
                    </div>
                    <span class="live-signal-direction">${signal.direction || 'WAIT'}</span>
                </div>
                <div class="live-signal-metrics">
                    <div><span>Score</span><strong>${signal.confluence_score ?? '--'}/100</strong></div>
                    <div><span>Conf.</span><strong>${signal.confidence ?? '--'}%</strong></div>
                    <div><span>R/R</span><strong>1:${Number(signal.risk_reward || 0).toFixed(2)}</strong></div>
                </div>
                <div class="live-signal-levels">
                    <div><span>Entrada</span><strong>${this.formatPrice(signal.entry)}</strong></div>
                    <div><span>Stop</span><strong>${this.formatPrice(signal.stop_loss)}</strong></div>
                    <div><span>Take 1</span><strong>${this.formatPrice(signal.take_profit_1)}</strong></div>
                    <div><span>Take 2</span><strong>${this.formatPrice(signal.take_profit_2)}</strong></div>
                    <div><span>Take 3</span><strong>${this.formatPrice(signal.take_profit_3)}</strong></div>
                    <div><span>Parcial</span><strong>${signal.partial_result || '--'}</strong></div>
                </div>
                <p class="live-signal-reason">${signal.explanation || signal.technical_reason || '--'}</p>
                <div class="live-signal-status">
                    <span>${this.signalStatusText(signal.status)}</span>
                    <span>${this.remainingSignalTime(signal.expires_at)}</span>
                </div>
            </article>
        `;
    }

    signalStatusText(status) {
        const map = {
            analyzing: 'Analisando',
            waiting_confirmation: 'Aguardando',
            active: 'Ativo',
            confirmed: 'Confirmado',
            invalidated: 'Invalidado',
            tp1_hit: 'TP1 atingido',
            tp2_hit: 'TP2 atingido',
            tp3_hit: 'TP3 atingido',
            stopped: 'Stop atingido',
            closed: 'Fechado',
        };
        return map[status] || status || '--';
    }

    remainingSignalTime(expiresAt) {
        if (!expiresAt) return '--';
        const diff = new Date(expiresAt).getTime() - Date.now();
        if (diff <= 0) return 'expirando';
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
    }

    renderMessages(messages) {
        const feed = document.getElementById('liveMessageFeed');
        if (!feed) return;
        feed.innerHTML = '';
        const items = messages.length ? messages : ['Aguardando leitura da IA...'];
        items.forEach((message) => {
            const row = document.createElement('div');
            row.className = 'live-message-row';
            row.innerHTML = `<i class="fas fa-circle"></i><span>${message}</span>`;
            feed.appendChild(row);
        });
    }

    renderInvalidations(invalidations) {
        const list = document.getElementById('liveInvalidations');
        if (!list) return;
        list.innerHTML = '';
        const items = invalidations.length ? invalidations : ['Sem invalidacao critica no momento.'];
        items.forEach((message) => {
            const row = document.createElement('div');
            row.className = 'live-invalidation-row';
            row.innerHTML = `<i class="fas fa-times-circle"></i><span>${message}</span>`;
            list.appendChild(row);
        });
    }

    renderPriceLines(data) {
        this.clearPriceLines();
        [
            { price: data.entry_aggressive, title: 'Entrada', color: '#38BDF8' },
            { price: data.entry_conservative, title: 'Entrada Cons.', color: '#F59E0B' },
            { price: data.stop_loss, title: 'Stop', color: '#EF4444' },
            { price: data.take_profit, title: 'Take', color: '#22C55E' },
        ].forEach((line) => {
            if (!Number.isFinite(Number(line.price))) return;
            this.priceLines.push(this.candleSeries.createPriceLine({
                price: Number(line.price),
                color: line.color,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: line.title,
            }));
        });
    }

    clearPriceLines() {
        this.priceLines.forEach((line) => this.candleSeries?.removePriceLine(line));
        this.priceLines = [];
    }

    isSupportResistanceBroken(price) {
        const resistance = Number(this.supportResistance.nearest_resistance);
        const support = Number(this.supportResistance.nearest_support);
        return (Number.isFinite(resistance) && price > resistance) || (Number.isFinite(support) && price < support);
    }

    getMarketStatusText(status) {
        const map = {
            open: 'ABERTO',
            closed: 'FECHADO',
            no_data: 'SEM DADOS',
            fallback: 'FALLBACK',
            unknown: 'INDEFINIDO',
        };
        return map[status] || String(status || '--').toUpperCase();
    }

    applyStateVisual(state) {
        const card = document.getElementById('liveStatusCard');
        if (!card) return;
        card.dataset.state = state;
    }

    handleAlerts(alerts, label) {
        const signature = alerts.join('|');
        if (!signature || signature === this.lastAlertSignature) return;
        this.lastAlertSignature = signature;
        this.showToast(label, alerts.includes('HIGH_RISK') || alerts.includes('INVALIDATED') ? 'error' : 'success');
        if (this.soundEnabled) this.playAlertSound(alerts);
    }

    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        const button = document.getElementById('liveSoundToggle');
        if (button) button.innerHTML = `<i class="fas fa-volume-${this.soundEnabled ? 'up' : 'mute'}"></i>`;
        if (this.soundEnabled) this.playAlertSound([]);
    }

    playAlertSound(alerts) {
        try {
            const context = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            oscillator.frequency.value = alerts.includes('HIGH_RISK') || alerts.includes('INVALIDATED') ? 220 : 660;
            gain.gain.value = 0.05;
            oscillator.connect(gain);
            gain.connect(context.destination);
            oscillator.start();
            setTimeout(() => {
                oscillator.stop();
                context.close();
            }, 180);
        } catch (error) {
            console.warn('Audio indisponivel', error);
        }
    }

    startCountdown() {
        clearInterval(this.countdownTimer);
        this.countdownTimer = setInterval(() => {
            const seconds = this.timeframeSeconds[this.timeframe] || 900;
            const now = Math.floor(Date.now() / 1000);
            const candleStart = this.lastCandleTime || Math.floor(now / seconds) * seconds;
            const remaining = Math.max(0, candleStart + seconds - now);
            const minutes = Math.floor(remaining / 60);
            const secs = remaining % 60;
            this.setText('liveCountdown', `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`);
        }, 1000);
    }

    setStatusLoading(loading) {
        const card = document.getElementById('liveStatusCard');
        if (card) card.classList.toggle('is-loading', loading);
    }

    setConnection(text) {
        this.setText('liveConnection', text);
    }

    pushMessage(message) {
        const feed = document.getElementById('liveMessageFeed');
        if (!feed) return;
        const row = document.createElement('div');
        row.className = 'live-message-row';
        row.innerHTML = `<i class="fas fa-circle"></i><span>${message}</span>`;
        feed.prepend(row);
        while (feed.children.length > 8) feed.lastElementChild.remove();
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3200);
    }

    setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value ?? '--';
    }

    formatPrice(price) {
        const value = Number(price);
        if (!Number.isFinite(value) || value === 0) return '--';
        const digits = value >= 1000 ? 2 : value >= 1 ? 4 : 6;
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new LiveTradingDashboard();
});
