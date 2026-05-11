class LiveTradingDashboard {
    constructor() {
        this.symbol = 'BTCUSDT';
        this.currentMarket = 'crypto';
        this.timeframe = '15m';
        this.chartEngine = null;
        this.marketDataEngine = new window.MarketDataEngine({ provider: 'bybit', fallbackProvider: 'binance', ttl: 6000 });
        this.websocketEngine = new window.WebSocketEngine({ provider: 'bybit', fallbackProvider: 'binance' });
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.lastCandles = [];
        this.socket = null;
        this.socketGeneration = 0;
        this.reconnectTimer = null;
        this.reconnectDelay = 2500;
        this.candleController = null;
        this.signalsController = null;
        this.statusController = null;
        this.statusTimer = null;
        this.candlePollTimer = null;
        this.tickPollTimer = null;
        this.countdownTimer = null;
        this.lastCandleTime = 0;
        this.lastAnalysisPrice = 0;
        this.lastAnalysisVolume = 0;
        this.lastAlertSignature = '';
        this.lastSignalAlertSignature = '';
        this.lastVoiceState = '';
        this.narrativeSignatures = new Set();
        this.soundEnabled = false;
        this.supportResistance = {};
        this.streaming = true;
        this.latestLiveStatus = null;
        this.elementCache = new Map();
        this.textCache = new Map();
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
        this.fetchExecutionStatus();
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
        document.getElementById('execArmBtn')?.addEventListener('click', () => this.updateExecutionMode(true));
        document.getElementById('execConfirmBtn')?.addEventListener('click', () => this.confirmExecution(false));
        document.getElementById('execKillBtn')?.addEventListener('click', () => this.killExecution());
        document.getElementById('execModeSelect')?.addEventListener('change', () => this.updateExecutionMode(false));
        window.addEventListener('resize', () => this.resizeChart());
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) return;
            if (this.streaming && (!this.socket || this.socket.readyState === WebSocket.CLOSED)) {
                this.connectStreams();
            }
            this.fetchLiveStatus('visibility_resume');
        });
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
        this.chartEngine = new window.LiveChartEngine('liveChart', { minHeight: 620 }).init();
        this.chart = this.chartEngine?.chart;
        this.candleSeries = this.chartEngine?.candleSeries;
        this.volumeSeries = this.chartEngine?.volumeSeries;
    }

    resizeChart() {
        this.chartEngine?.resize();
    }

    async resetLive(fit = false) {
        this.statusController?.abort();
        this.candleController?.abort();
        this.signalsController?.abort();
        clearInterval(this.candlePollTimer);
        clearInterval(this.tickPollTimer);
        clearTimeout(this.reconnectTimer);
        this.websocketEngine?.close();
        this.socket = null;
        this.socketGeneration += 1;
        this.reconnectDelay = 2500;
        this.chartEngine?.clearOverlays();
        this.narrativeSignatures.clear();
        this.setConnection('Atualizando');
        await this.loadInitialCandles(fit);
        this.fetchLiveStatus('change');
        this.connectStreams();
    }

    async loadInitialCandles(fit = false) {
        try {
            this.setConnection('Carregando');
            this.candleController?.abort();
            this.candleController = new AbortController();
            const data = await this.marketDataEngine.candles(this.symbol, this.timeframe, 240, this.candleController.signal);
            if (!data.success) throw new Error(data.error || 'candles_unavailable');
            const candles = Array.isArray(data.candles) ? data.candles : [];
            const volumes = Array.isArray(data.volumes) ? data.volumes : [];
            this.chartEngine?.setData(candles, volumes, fit);
            this.lastCandles = this.chartEngine?.lastCandles || candles;
            const last = candles[candles.length - 1] || {};
            this.streaming = data.streaming ?? String(this.symbol).endsWith('USDT');
            this.lastCandleTime = Number(last.time || 0);
            this.lastAnalysisPrice = Number(last.close || 0);
            this.setText('livePrice', this.formatPrice(last.close || data.ticker?.lastPrice || 0));
            this.setText('liveChartTitle', `${this.symbol} - ${String(data.source || '--').toUpperCase()} - ${this.timeframe}`);
            this.setText('liveDataSource', String(data.source || '--').toUpperCase());
            this.setText('liveMarketStatus', this.getMarketStatusText(data.market_status));
            if (data.market_message) this.pushMessage(data.market_message);
            this.setConnection(this.streaming ? 'Grafico ativo' : 'REST / historico');
        } catch (error) {
            if (error.name === 'AbortError') return;
            this.setConnection('REST falhou');
            this.pushMessage('Nao foi possivel carregar historico. Tentando manter a tela ativa.');
        }
    }

    connectStreams() {
        clearInterval(this.candlePollTimer);
        clearInterval(this.tickPollTimer);
        clearTimeout(this.reconnectTimer);
        this.socketGeneration += 1;
        if (!String(this.symbol).endsWith('USDT')) {
            this.websocketEngine?.close();
            this.socket = null;
            this.setConnection(this.streaming ? 'MT5 tempo real' : 'REST / historico');
            this.candlePollTimer = setInterval(() => this.loadInitialCandles(false), this.streaming ? 10000 : 60000);
            if (this.streaming) {
                this.refreshMarketTick();
                this.tickPollTimer = setInterval(() => this.refreshMarketTick(), 1500);
            }
            return;
        }
        if (!this.streaming) {
            this.websocketEngine?.close();
            this.socket = null;
            this.setConnection('REST / historico');
            this.candlePollTimer = setInterval(() => this.loadInitialCandles(false), 60000);
            return;
        }
        this.websocketEngine?.connectKline({
            symbol: this.symbol,
            timeframe: this.timeframe,
            onState: (state) => this.setConnection(state),
            onKline: (kline) => this.handleKline({ k: kline }),
        });
        this.socket = this.websocketEngine?.socket || null;
    }

    async refreshMarketTick() {
        try {
            const data = await this.marketDataEngine.tick(this.symbol, undefined, true);
            if (!data?.success) return;
            const price = Number(data.last || data.bid || data.ask);
            if (!Number.isFinite(price) || price <= 0) return;
            this.setText('livePrice', this.formatPrice(price));
            this.setText('liveDataSource', String(data.source || 'mt5').toUpperCase());
            this.updateCurrentCandleFromTick(data, price);
        } catch (error) {
            this.setConnection('MT5 aguardando');
        }
    }

    updateCurrentCandleFromTick(tick, price) {
        const seconds = this.timeframeSeconds[this.timeframe] || 900;
        const timestamp = Number(tick.time || Date.now() / 1000);
        const bucket = Math.floor(timestamp / seconds) * seconds;
        const last = this.lastCandles[this.lastCandles.length - 1];
        const sameBucket = last && Number(last.time) === bucket;
        const candle = sameBucket ? {
            ...last,
            high: Math.max(Number(last.high), price),
            low: Math.min(Number(last.low), price),
            close: price,
        } : {
            time: bucket,
            open: Number(last?.close || price),
            high: Math.max(Number(last?.close || price), price),
            low: Math.min(Number(last?.close || price), price),
            close: price,
        };
        const volume = {
            time: candle.time,
            value: Number(tick.volume || 0),
            color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.45)' : 'rgba(239, 83, 80, 0.45)',
        };
        this.chartEngine?.update(candle, volume);
        this.lastCandles = this.chartEngine?.lastCandles || this.lastCandles;
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
        this.chartEngine?.update(candle, volume);
        this.lastCandles = this.chartEngine?.lastCandles || this.lastCandles;
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
        this.latestLiveStatus = data;
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
        this.setText('liveDeskSummary', data.context?.narrative || data.message || '--');
        this.setText('liveDeskState', data.status || state);
        this.setText('liveDeskUpdated', this.formatClock(data.updated_at));
        this.renderContext(data.operational_panel || {}, data.context || {});
        this.setText('liveMarketStatus', this.getMarketStatusText(data.market_data_status || data.market_status));
        this.setText('liveDataSource', String(data.source || '--').toUpperCase());
        if (data.market_message) this.pushMessage(data.market_message);
        this.renderMessages(data.narrative_feed || data.messages || []);
        this.renderConfirmationFilters(data.confirmation_filters || data.invalidations || [], data.real_invalidations || []);
        this.supportResistance = data.support_resistance || {};
        this.renderPriceLines(data);
        const markers = window.VisualAIOverlays?.buildCompleteMarkers(this.lastCandles, {
            signal_cards: { active: data.probable_direction === 'BUY' ? 'buy' : data.probable_direction === 'SELL' ? 'sell' : 'wait', label: data.status },
            technical_reader: data.technical || {},
            smc: data.smc || {},
            volume_analysis: data.volume || {},
            tape_reading: data.tape_reading || {},
        }) || [];
        this.chartEngine?.applyMarkers([...markers, ...this.normalizeSmartMarkers(data.smart_overlays?.markers || [])]);
        this.applyStateVisual(state);
        this.handleAlerts(data.alerts || [], data.status || state);
        this.handleVoiceStatus(data);
        if (data.signal_event) this.renderSignalEvent(data.signal_event);
        this.renderLiveSignalsSnapshot(data.live_signals || {}, data.signal_event);
        this.evaluateExecution(data);
    }

    handleVoiceStatus(data) {
        const state = data?.state || '';
        if (!state || state === this.lastVoiceState) return;
        this.lastVoiceState = state;
        window.financeVoiceAssistant?.speakLiveStatus(data);
    }

    renderContext(panel, context) {
        this.setText('liveContextBias', panel.bias || context.operational_bias || '--');
        this.setText('liveContextStructure', panel.structure || context.market_structure || '--');
        this.setText('liveContextLiquidity', panel.liquidity || '--');
        this.setText('liveContextPressure', panel.pressure || context.pressure || '--');
        this.setText('liveContextBos', this.eventLevel(panel.last_bos || context.last_bos));
        this.setText('liveContextChoch', this.eventLevel(panel.last_choch || context.last_choch));
        this.setText('liveInvalidationLevel', this.formatPrice(panel.invalidation || context.invalidation));
    }

    fetchSignals() {
        this.signalsController?.abort();
        this.signalsController = new AbortController();
        fetch(`/api/live/signals?symbol=${encodeURIComponent(this.symbol)}&timeframe=${encodeURIComponent(this.timeframe)}`, {
            signal: this.signalsController.signal,
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data?.success) return;
                this.renderSignals(data.active || []);
                this.renderSignalEvent(data.signal);
                this.setText('liveSignalsCount', data.stats?.active_count ?? 0);
                this.setText('liveSignalsBadge', `${data.stats?.active_count ?? 0} oportunidades em tempo real`);
            })
            .catch((error) => {
                if (error.name !== 'AbortError') console.warn('Sinais live indisponiveis', error);
            });
    }

    renderLiveSignalsSnapshot(snapshot, signalEvent) {
        const active = Array.isArray(snapshot.active) ? snapshot.active : [];
        this.renderSignals(active);
        this.renderSignalEvent(signalEvent);
        const stats = snapshot.stats || {};
        const activeCount = stats.active_count ?? active.length;
        this.setText('liveSignalsCount', activeCount);
        this.setText('liveSignalsBadge', `${activeCount} oportunidades em tempo real`);
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
                        <h4>${signal.symbol || signal.asset} - ${signal.timeframe}</h4>
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
        const items = messages.length ? messages : ['Aguardando leitura da IA...'];
        if (!Array.isArray(messages) || !messages.length || typeof items[0] === 'string') {
            feed.innerHTML = '';
        }
        items.forEach((item) => {
            const message = typeof item === 'string' ? item : item.text;
            const signature = `${typeof item === 'string' ? 'IA' : item.kind}:${message}`;
            if (typeof item !== 'string' && this.narrativeSignatures.has(signature)) return;
            this.narrativeSignatures.add(signature);
            const row = document.createElement('div');
            row.className = `live-message-row ${typeof item === 'string' ? 'info' : item.severity || 'info'}`;
            row.innerHTML = `
                <i class="fas fa-circle"></i>
                <span>
                    <small>${typeof item === 'string' ? this.clockNow() : this.formatClock(item.timestamp)} - ${typeof item === 'string' ? 'IA' : item.kind}</small>
                    ${message}
                </span>
            `;
            feed.appendChild(row);
        });
        while (feed.children.length > 24) feed.firstElementChild.remove();
        feed.scrollTop = feed.scrollHeight;
    }

    renderConfirmationFilters(filters, realInvalidations = []) {
        const list = document.getElementById('liveInvalidations');
        if (!list) return;
        list.innerHTML = '';
        const items = filters.length ? filters : ['Sem filtros bloqueando no momento.'];
        items.forEach((message) => {
            const row = document.createElement('div');
            row.className = 'live-invalidation-row filter';
            row.innerHTML = `<i class="fas fa-hourglass-half"></i><span>${message}</span>`;
            list.appendChild(row);
        });
        realInvalidations.forEach((message) => {
            const row = document.createElement('div');
            row.className = 'live-invalidation-row critical';
            row.innerHTML = `<i class="fas fa-times-circle"></i><span>Invalidacao real: ${message}</span>`;
            list.appendChild(row);
        });
    }

    fetchExecutionStatus() {
        fetch('/api/execution/status')
            .then((response) => response.json())
            .then((data) => this.renderExecutionStatus(data))
            .catch(() => this.setText('execDecision', 'Execucao indisponivel no momento.'));
    }

    updateExecutionMode(enable) {
        const mode = document.getElementById('execModeSelect')?.value || 'alert';
        fetch('/api/execution/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enable, mode }),
        })
            .then((response) => response.json())
            .then((data) => this.renderExecutionStatus(data))
            .catch(() => this.setText('execDecision', 'Nao foi possivel atualizar execucao.'));
    }

    killExecution() {
        fetch('/api/execution/kill-switch', { method: 'POST' })
            .then((response) => response.json())
            .then((data) => this.renderExecutionStatus(data))
            .catch(() => this.setText('execDecision', 'Kill switch indisponivel.'));
    }

    evaluateExecution(status) {
        if (!status?.success) return;
        fetch('/api/execution/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ live_status: status }),
        })
            .then((response) => response.json())
            .then((data) => this.renderExecutionStatus(data))
            .catch(() => {});
    }

    confirmExecution(real = false) {
        if (!this.latestLiveStatus) {
            this.setText('execDecision', 'Sem sinal live para confirmar.');
            return;
        }
        fetch('/api/execution/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ live_status: this.latestLiveStatus, real }),
        })
            .then((response) => response.json())
            .then((data) => {
                this.renderExecutionStatus(data);
                if (data.success) {
                    this.showToast(data.paper ? 'Ordem paper registrada.' : 'Ordem enviada ao broker.', 'success');
                }
            })
            .catch(() => this.setText('execDecision', 'Falha ao confirmar ordem.'));
    }

    renderExecutionStatus(data) {
        if (!data) return;
        const status = data.status || data;
        const risk = status.risk || {};
        this.setText('execEnabled', status.enabled ? 'LIGADO' : 'DESLIGADO');
        this.setText('execMode', String(status.mode || 'alert').toUpperCase());
        this.setText('execRisk', `${Number(risk.risk_per_trade_pct || 0).toFixed(2)}%`);
        this.setText('execTradesToday', status.trades_today ?? 0);
        this.setText('execDailyLoss', `${Number(status.daily_loss_pct || 0).toFixed(2)}%`);
        this.setText('execLastOrder', status.last_order?.id || '--');
        const brokerText = status.real_enabled ? 'Real habilitado por .env' : 'Paper trading';
        this.setText('execDecision', data.decision?.reason || status.last_rejection || `${brokerText}. ${status.message || 'Aguardando sinal IA.'}`);
        const select = document.getElementById('execModeSelect');
        if (select && status.mode) select.value = status.mode;
    }

    renderPriceLines(data) {
        const smartLevels = Array.isArray(data.smart_overlays?.levels) ? data.smart_overlays.levels.map((line) => ({
            price: line.price,
            label: line.label,
            color: line.color,
        })) : [];
        const levels = [
            { price: data.entry_aggressive, label: 'Entrada', color: '#38BDF8' },
            { price: data.entry_conservative, label: 'Entrada Cons.', color: '#F59E0B' },
            { price: data.stop_loss, label: 'Stop', color: '#EF4444' },
            { price: data.take_profit, label: 'Take', color: '#22C55E' },
            ...smartLevels,
        ];
        this.chartEngine?.applyLevels(levels);
        this.chartEngine?.applyZones(data.smart_overlays?.zones || []);
    }

    clearPriceLines() {
        this.chartEngine?.clearLineMap(this.chartEngine.priceLines);
    }

    renderZoneLines(zone) {
        this.chartEngine?.applyZones([zone]);
    }

    clearOverlayLines() {
        this.chartEngine?.clearLineMap(this.chartEngine.overlayLines);
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
        const next = value ?? '--';
        if (this.textCache.get(id) === next) return;
        this.textCache.set(id, next);
        let element = this.elementCache.get(id);
        if (!element) {
            element = document.getElementById(id);
            if (element) this.elementCache.set(id, element);
        }
        if (element) element.textContent = value ?? '--';
    }

    normalizeSmartMarkers(markers) {
        if (!Array.isArray(markers)) return [];
        return markers
            .filter((marker) => marker?.time && marker?.text)
            .map((marker) => ({
                time: marker.time,
                position: marker.position || 'aboveBar',
                shape: marker.shape || 'circle',
                color: marker.color || '#38bdf8',
                text: marker.text,
            }));
    }

    eventLevel(event) {
        if (!event) return '--';
        const side = event.side ? String(event.side).toUpperCase() : 'OK';
        const level = this.formatPrice(event.level);
        return level === '--' ? side : `${side} ${level}`;
    }

    formatClock(value) {
        const date = value ? new Date(value) : new Date();
        if (Number.isNaN(date.getTime())) return '--';
        return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    clockNow() {
        return this.formatClock(new Date().toISOString());
    }

    withAlpha(color, alpha) {
        const hex = String(color || '').replace('#', '');
        if (hex.length !== 6) return color;
        const value = Math.round(Math.max(0.08, Math.min(alpha, 0.9)) * 255).toString(16).padStart(2, '0');
        return `#${hex}${value}`;
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
