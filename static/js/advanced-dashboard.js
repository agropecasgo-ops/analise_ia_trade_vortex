class AdvancedDashboard {
    constructor() {
        this.currentAsset = 'BTCUSDT';
        this.currentMarket = 'crypto';
        this.currentTimeframe = '1h';
        this.chartEngine = null;
        this.marketDataEngine = new window.MarketDataEngine({ provider: 'bybit', fallbackProvider: 'binance', ttl: 8000 });
        this.websocketEngine = new window.WebSocketEngine({ provider: 'bybit', fallbackProvider: 'binance' });
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.overlaySeries = {};
        this.priceLines = [];
        this.refreshTimer = null;
        this.klineSocket = null;
        this.tradeWindow = [];
        this.alerts = [];
        this.triggeredAlerts = new Set();
        this.equityChart = null;
        this.equitySeries = null;
        this.isLoading = false;
        this.operationalState = 'loading';
        this.lastInvalidationToast = { signature: null, time: 0 };
        this.refreshMs = 10000;
        this.requestSeq = 0;
        this.candleController = null;
        this.analysisController = null;
        this.localCacheTtl = 8000;
        this.analysisTimeoutMs = 12000;
        this.candleMemoryCache = new Map();
        this.analysisMemoryCache = new Map();
        this.latestStreaming = true;
        this.realtimeAnalysisTimer = null;
        this.init();
    }

    async init() {
        this.setupChart();
        this.setupEventListeners();
        await this.loadAssets();
        await this.updateDashboard();
        this.startRealtime();
    }

    setupEventListeners() {
        const assetSelect = document.getElementById('assetSelect');
        const marketSelect = document.getElementById('marketSelect');
        marketSelect?.addEventListener('change', async (event) => {
            this.currentMarket = event.target.value;
            await this.loadAssets();
            this.updateDashboard(true);
        });
        assetSelect?.addEventListener('change', (event) => {
            this.currentAsset = event.target.value;
            this.updateDashboard();
        });

        document.querySelectorAll('.tf-btn').forEach((button) => {
            button.addEventListener('click', (event) => {
                document.querySelectorAll('.tf-btn').forEach((btn) => btn.classList.remove('active'));
                event.currentTarget.classList.add('active');
                this.currentTimeframe = event.currentTarget.dataset.tf;
                this.updateDashboard(true);
            });
        });

        document.getElementById('btnRunBacktest')?.addEventListener('click', () => this.runBacktest());
        document.getElementById('btnAddWatch')?.addEventListener('click', () => this.addCurrentToWatchlist());
        document.getElementById('btnCreateAlert')?.addEventListener('click', () => this.createPriceAlert());
        document.querySelector('[data-chart-action="fit"]')?.addEventListener('click', () => this.chart?.timeScale().fitContent());
        window.addEventListener('resize', () => this.resizeChart());
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().catch(() => {});
        }
    }

    async loadAssets() {
        const response = await fetch(`/api/assets?market=${encodeURIComponent(this.currentMarket)}`);
        const data = await response.json();
        const select = document.getElementById('assetSelect');
        const marketSelect = document.getElementById('marketSelect');
        if (!data.success || !select) return;

        if (marketSelect && Array.isArray(data.markets)) {
            marketSelect.innerHTML = data.markets.map((market) => (
                `<option value="${market.key}">${market.label}</option>`
            )).join('');
            marketSelect.value = this.currentMarket;
        }

        select.innerHTML = data.assets.map((asset) => (
            `<option value="${asset.symbol}">${asset.symbol} - ${asset.name}</option>`
        )).join('');
        if (!data.assets.some((asset) => asset.symbol === this.currentAsset)) {
            this.currentAsset = data.assets[0]?.symbol || 'BTCUSDT';
        }
        select.value = this.currentAsset;
    }

    setupChart() {
        this.chartEngine = new window.InstitutionalChartEngine('chart-container', {
            minHeight: 520,
            watermark: {
                visible: true,
                text: 'BINANCE REAL-TIME',
                color: 'rgba(56, 189, 248, 0.13)',
                fontSize: 18,
                horzAlign: 'right',
                vertAlign: 'bottom',
            },
            indicators: {
                ema9: { color: '#FACC15', lineWidth: 2, title: 'EMA 9' },
                ema21: { color: '#38BDF8', lineWidth: 2, title: 'EMA 21' },
                ema200: { color: '#F59E0B', lineWidth: 2, title: 'EMA 200' },
                vwap: { color: '#22D3EE', lineWidth: 2, title: 'VWAP' },
                bollinger_upper: { color: 'rgba(148, 163, 184, 0.8)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted },
                bollinger_middle: { color: 'rgba(148, 163, 184, 0.45)', lineWidth: 1 },
                bollinger_lower: { color: 'rgba(148, 163, 184, 0.8)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted },
            },
        }).init();
        this.chart = this.chartEngine?.chart;
        this.candleSeries = this.chartEngine?.candleSeries;
        this.volumeSeries = this.chartEngine?.volumeSeries;
        this.overlaySeries = this.chartEngine?.indicatorSeries || {};
    }

    resizeChart() {
        this.chartEngine?.resize();
    }

    startRealtime() {
        clearInterval(this.refreshTimer);
        this.refreshTimer = setInterval(() => this.updateDashboard(false), this.refreshMs);
    }

    async updateDashboard(fit = false) {
        this.requestSeq += 1;
        const seq = this.requestSeq;
        this.candleController?.abort();
        this.analysisController?.abort();
        this.candleController = new AbortController();
        this.analysisController = new AbortController();
        this.isLoading = true;
        this.setConnectionState('Atualizando');
        this.setChartLoading('Carregando grafico...');
        this.setOperationalState({
            state: 'loading',
            message: 'Analisando IA...'
        });

        try {
            const candles = await this.fetchCandles(this.currentAsset, this.currentTimeframe, 200, this.candleController.signal);
            if (seq !== this.requestSeq) return;
            if (!candles.success) throw new Error(candles.error || 'Erro nos candles');

            this.latestStreaming = candles.streaming ?? String(this.currentAsset).endsWith('USDT');
            this.updateChart(candles, null, fit);
            this.setChartLoading('');
            this.connectMarketStreams();

            let analysis = this.createNeutralAnalysis(candles);
            this.updateAnalysisPanel(analysis, candles);
            this.loadAnalysisInBackground(candles, seq);
            Promise.allSettled([this.updateMultiTimeframe(), this.updateHeatmap(), this.loadWatchlist(), this.loadAlerts()]);
            this.setConnectionState('Tempo real');
        } catch (error) {
            if (error.name === 'AbortError') return;
            console.error(error);
            this.setConnectionState('Falha');
            this.setChartLoading('Nao foi possivel carregar candles.');
            this.showNotification(`Erro ao atualizar: ${error.message}`, 'error');
        } finally {
            if (seq === this.requestSeq) this.isLoading = false;
        }
    }

    async loadAnalysisInBackground(candles, seq) {
        this.setOperationalState({ state: 'loading', message: 'Analisando IA...' });
        try {
            const analysis = await this.withTimeout(
                this.fetchAnalysis(this.currentAsset, this.currentTimeframe, this.analysisController.signal),
                this.analysisTimeoutMs,
                'Tempo limite da IA atingido'
            );
            if (seq !== this.requestSeq) return;
            const payload = analysis?.success ? analysis : this.createNeutralAnalysis(candles);
            this.updateChart(candles, payload, false);
            this.updateAnalysisPanel(payload, candles);
        } catch (error) {
            if (error.name === 'AbortError') return;
            console.warn('Falha na IA, mantendo grafico:', error);
            if (seq === this.requestSeq) {
                this.updateAnalysisPanel(this.createNeutralAnalysis(candles), candles);
            }
        }
    }

    withTimeout(promise, timeoutMs, message) {
        let timeoutId;
        const timeout = new Promise((_, reject) => {
            timeoutId = setTimeout(() => reject(new Error(message)), timeoutMs);
        });
        return Promise.race([promise, timeout]).finally(() => clearTimeout(timeoutId));
    }

    async fetchCandles(symbol, timeframe, limit, signal) {
        return this.marketDataEngine.candles(symbol, timeframe, limit, signal);
    }

    async fetchAnalysis(symbol, timeframe, signal, force = false) {
        return this.marketDataEngine.analysis(symbol, timeframe, signal, force);
    }

    getLocalCache(cache, key) {
        const record = cache.get(key);
        if (!record || Date.now() - record.time > this.localCacheTtl) {
            cache.delete(key);
            return null;
        }
        return record.data;
    }

    setLocalCache(cache, key, data) {
        cache.set(key, { time: Date.now(), data });
    }

    setChartLoading(message) {
        const container = document.getElementById('chart-container');
        if (!container) return;
        let overlay = container.querySelector('.chart-loading');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'chart-loading';
            container.appendChild(overlay);
        }
        overlay.textContent = message || '';
        overlay.style.display = message ? 'grid' : 'none';
    }

    updateChart(candles, analysis, fit = false) {
        const candleData = Array.isArray(candles?.candles) ? candles.candles.filter(Boolean) : [];
        const volumeData = Array.isArray(candles?.volumes) ? candles.volumes.filter(Boolean) : [];
        if (!candleData.length) {
            this.setOperationalState({ state: 'neutral', message: 'Sem candles validos para renderizar.' });
            return;
        }
        this.chartEngine?.setData(candleData, volumeData, fit);
        this.chartEngine?.setIndicators(candles.overlays || {});

        this.applyInstitutionalOverlays(analysis);
        const baseMarkers = Array.isArray(analysis?.markers) ? analysis.markers : [];
        const aiMarkers = window.VisualAIOverlays?.buildCompleteMarkers(candleData, analysis) || [];
        this.chartEngine?.applyMarkers([...baseMarkers, ...aiMarkers]);
    }

    applyInstitutionalOverlays(analysis) {
        if (!analysis) {
            this.chartEngine?.applyLevels([]);
            this.chartEngine?.applyZones([]);
            return;
        }

        const institutionalAI = analysis.institutional_ai || {};
        const institutionalDecision = analysis.institutional_decision || {};
        const institutionalRisk = institutionalDecision.risk_plan || institutionalAI.risk || analysis.institutional_risk || {};
        const operationalSignal = analysis.operational_signal || institutionalAI.signal || {};
        const levels = analysis.levels || {};

        const overlayLevels = [
            { label: 'Entrada', price: institutionalRisk.entry ?? operationalSignal.entry ?? operationalSignal.entry_aggressive ?? levels.entrada, color: '#38BDF8' },
            { label: 'Entrada Cons.', price: operationalSignal.entry_conservative, color: '#60A5FA', lineWidth: 1 },
            { label: 'Stop', price: institutionalRisk.stop_loss ?? institutionalRisk.stop ?? operationalSignal.stop_loss ?? levels.stop_loss, color: '#EF4444' },
            { label: 'Take 1', price: institutionalRisk.take_profit ?? operationalSignal.take_profit_1 ?? levels.alvo_1, color: '#22C55E' },
            { label: 'Take Parcial', price: institutionalRisk.take_partial ?? institutionalRisk.partial_take ?? operationalSignal.partial_take, color: '#F59E0B', lineWidth: 1 },
            { label: 'Invalidacao', price: institutionalRisk.invalidation ?? operationalSignal.invalidation, color: '#F97316' },
        ].filter((level) => Number.isFinite(Number(level.price)));

        const smc = institutionalAI.smc || analysis.smc || {};
        const context = institutionalAI.context || analysis.institutional_context || {};
        const zones = [
            this.normalizeOverlayZone(context.relevant_order_block || smc.relevant_order_block || smc.nearest_order_block, 'OB', '#A78BFA', 0.22, true),
            this.normalizeOverlayZone(context.relevant_fvg || smc.relevant_fvg, 'FVG', '#F59E0B', 0.2, true),
            this.normalizeOverlayZone(context.liquidity_zone || smc.liquidity_zone, 'Liquidez', '#38BDF8', 0.18, false),
            this.normalizeOverlayZone(smc.liquidity_sweep?.zone || context.liquidity_sweep?.zone, 'Sweep', '#D946EF', 0.3, true),
        ].filter(Boolean);

        this.chartEngine?.applyLevels(overlayLevels);
        this.chartEngine?.applyZones(zones);
    }

    normalizeOverlayZone(zone, label, color, opacity, active = false) {
        if (!zone) return null;
        const low = Number(zone.low ?? zone.bottom ?? zone.min ?? zone.price_low ?? zone.start ?? zone.price);
        const high = Number(zone.high ?? zone.top ?? zone.max ?? zone.price_high ?? zone.end ?? zone.price);
        if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
        return {
            label,
            type: String(zone.type || label).toLowerCase(),
            low: Math.min(low, high),
            high: Math.max(low, high),
            color,
            opacity,
            active: Boolean(zone.active ?? active),
        };
    }

    createNeutralAnalysis(candlesPayload) {
        const lastCandle = Array.isArray(candlesPayload?.candles) && candlesPayload.candles.length
            ? candlesPayload.candles[candlesPayload.candles.length - 1]
            : { close: 0 };
        const price = Number(lastCandle.close || candlesPayload?.ticker?.lastPrice || 0);
        return {
            success: true,
            symbol: this.currentAsset,
            timeframe: this.currentTimeframe,
            source: candlesPayload?.source || '--',
            market_status: candlesPayload?.market_status || 'unknown',
            market_message: candlesPayload?.market_message || '',
            streaming: candlesPayload?.streaming ?? String(this.currentAsset).endsWith('USDT'),
            current_price: price,
            price_change: Number(candlesPayload?.ticker?.priceChangePercent || 0),
            signal: {
                signal_type: 'neutro',
                confidence: 0,
                indicators: {
                    rsi: 50,
                    macd: 0,
                    atr: 0,
                    volume: 0,
                    vwap: price,
                    ema9: price,
                    ema21: price,
                    bollinger_lower: price,
                    bollinger_upper: price,
                },
            },
            levels: {},
            support_resistance: [],
            candle_reading: [],
            reasoning: ['Analise indisponivel. Grafico mantido em modo neutro.'],
            operational_score: 0,
            final_score: {
                score: 0,
                confidence: 0,
                signal: 'NEUTRAL',
                classification: 'Nao operar',
                entry_aggressive: false,
                entry_conservative: false,
                technical_reasons: ['Grafico renderizado sem dependencia da IA.'],
                invalidation_reasons: [],
            },
            validation: { entry_quality: { quality: 'neutra', probability: 0, invalidated: false } },
            smc: {},
            wyckoff: {},
            elliott_wave: {},
            tape_reading: {},
            advanced_confluence: {},
            institutional_context: {},
            volume_analysis: {},
            signal_cards: {
                active: 'wait',
                label: 'AGUARDAR CONFIRMACAO',
                confidence: 35,
                score: 0,
                intensity: 'carregando',
                reason: 'Aguardando analise da IA Completa.',
            },
            operational_state: {
                state: 'loading',
                message: 'Analisando IA...',
                ready: false,
            },
        };
    }

    connectMarketStreams() {
        if (this.latestStreaming === false || !String(this.currentAsset).endsWith('USDT')) {
            this.websocketEngine?.close();
            this.klineSocket = null;
            this.setConnectionState('REST / historico');
            return;
        }

        this.websocketEngine?.connectKline({
            symbol: this.currentAsset,
            timeframe: this.currentTimeframe,
            includeTrades: true,
            onState: (state) => this.setConnectionState(state),
            onTrade: (trade) => this.handleTradeStream(trade),
            onKline: (kline) => {
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
                this.setText('currentPrice', this.formatPrice(candle.close));
                this.setText('lastUpdate', new Date().toLocaleTimeString('pt-BR'));
                if (kline.x) this.scheduleRealtimeAnalysis();
            },
        });
        this.klineSocket = this.websocketEngine?.socket || null;
    }

    handleTradeStream(trade) {
        if (!trade?.p) return;
        const price = Number(trade.p);
        const quantity = Number(trade.q);
        const side = trade.m ? 'sell' : 'buy';
        const now = Date.now();
        this.tradeWindow.push(now);
        this.tradeWindow = this.tradeWindow.filter((time) => now - time < 1000);
        this.setText('tradeSpeed', this.tradeWindow.length);
        this.checkRealtimeAlerts(price);

        const tape = document.getElementById('tradeTape');
        if (!tape) return;
        const row = document.createElement('div');
        row.className = `trade-row ${side}`;
        row.innerHTML = `
            <span>${side.toUpperCase()}</span>
            <span>${this.formatPrice(price)}</span>
            <span>${this.formatCompact(quantity)}</span>
        `;
        tape.prepend(row);
        while (tape.children.length > 24) tape.lastElementChild.remove();
    }

    checkRealtimeAlerts(price) {
        this.alerts.forEach((alert) => {
            if (!alert.active || alert.symbol !== this.currentAsset || this.triggeredAlerts.has(alert.id)) return;
            const target = Number(alert.target);
            const hit = alert.condition_type === 'price_above'
                ? price >= target
                : alert.condition_type === 'price_below'
                    ? price <= target
                    : Math.abs(price - target) / target < 0.0005;
            if (!hit) return;
            this.triggeredAlerts.add(alert.id);
            const message = `Alerta ${alert.symbol}: preco ${this.formatPrice(price)} atingiu ${this.formatPrice(target)}`;
            this.showNotification(message, 'success');
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('FinanceAI', { body: message });
            }
            fetch('/api/telegram/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            }).catch(() => {});
        });
    }

    clearPriceLines() {
        this.priceLines.forEach((line) => this.candleSeries.removePriceLine(line));
        this.priceLines = [];
    }

    addTradePriceLines(levels) {
        const lines = [
            { key: 'entrada', title: 'Entrada', color: '#38BDF8' },
            { key: 'stop_loss', title: 'Stop', color: '#EF4444' },
            { key: 'alvo_1', title: 'Take 1', color: '#22C55E' },
            { key: 'alvo_2', title: 'Take 2', color: '#F59E0B' },
        ];
        lines.forEach((line) => {
            if (!Number.isFinite(levels[line.key])) return;
            const priceLine = this.candleSeries.createPriceLine({
                price: levels[line.key],
                color: line.color,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: line.title,
            });
            this.priceLines.push(priceLine);
        });
    }

    addInstitutionalPriceLines(analysis) {
        const context = analysis.institutional_context || analysis || {};
        const smc = analysis.smc || {};
        const zones = [
            { zone: context.relevant_order_block || smc.relevant_order_block || smc.nearest_order_block, title: 'SMC OB', color: '#a78bfa' },
            { zone: context.relevant_fvg || smc.relevant_fvg, title: 'SMC FVG', color: '#f59e0b' },
            { zone: context.liquidity_zone || smc.liquidity_zone, title: 'Liquidez', color: '#38bdf8' },
        ];
        zones.forEach((item) => {
            const price = this.zonePrice(item.zone);
            if (!Number.isFinite(price)) return;
            const priceLine = this.candleSeries.createPriceLine({
                price,
                color: item.color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: item.title,
            });
            this.priceLines.push(priceLine);
        });
    }

    updateAnalysisPanel(analysis, candlesPayload) {
        analysis = analysis || this.createNeutralAnalysis(candlesPayload);
        const signal = analysis.signal || {};
        const indicators = signal.indicators || {};
        const ticker = analysis.ticker || candlesPayload.ticker || {};
        const source = analysis.source || candlesPayload.source || '--';
        const marketStatus = analysis.market_status || candlesPayload.market_status || '--';
        const marketMessage = analysis.market_message || candlesPayload.market_message || '';
        const confluenceAI = analysis.confluence_ai || {};
        const operationalSignal = analysis.operational_signal || {};
        const institutionalDecision = analysis.institutional_decision || {};
        const institutionalRisk = institutionalDecision.risk_plan || {};
        const finalScore = analysis.final_score || {};
        const score = Number(institutionalDecision.score ?? operationalSignal.score ?? confluenceAI.score ?? analysis.operational_score ?? 0);
        const gaugeScore = institutionalDecision.score != null ? score : confluenceAI.score != null ? score : Number(analysis.operational_score || 0);
        const finalScore10 = Number(confluenceAI.score != null ? (score / 10) : (finalScore.score ?? (gaugeScore / 10)));
        const mtfConfluence = analysis.multi_timeframe?.confluence;
        const finalDecision = this.deriveFinalSignalDecision(analysis, signal, gaugeScore);

        this.latestStreaming = analysis.streaming ?? candlesPayload.streaming ?? this.latestStreaming;
        this.setText('chartTitle', `${analysis.symbol} · ${String(source).toUpperCase()} · ${analysis.timeframe}`);
        this.setText('currentPrice', this.formatPrice(analysis.current_price));
        this.setText('priceChange', `${Number(ticker.priceChangePercent || analysis.price_change || 0).toFixed(2)}%`);
        this.setText('dataSource', String(source).toUpperCase());
        this.setText('marketState', this.getMarketStatusText(marketStatus));
        this.setText('operationalScore', `${Math.round(gaugeScore)}/100`);
        this.setText('scoreValue', finalScore10.toFixed(1));
        this.setText('finalScoreValue', finalScore10.toFixed(1));
        this.setText('scoreText', institutionalDecision.narrative || operationalSignal.status || confluenceAI.classification || finalScore.classification || (gaugeScore > 70 ? 'Alta qualidade' : gaugeScore > 50 ? 'Aguardando confirmacao' : 'Risco elevado'));
        this.updateGauge(gaugeScore);

        this.setText('mainSignal', finalDecision.label);
        this.setSignalVisualState(finalDecision);
        this.setText('confidenceValue', `${Math.round(finalDecision.confidence)}%`);
        this.setText('entryAggressive', operationalSignal.entry_aggressive ? this.formatPrice(operationalSignal.entry_aggressive) : 'NAO');
        this.setText('entryConservative', operationalSignal.entry_conservative ? this.formatPrice(operationalSignal.entry_conservative) : 'NAO');
        this.setText('riskDisclaimer', operationalSignal.disclaimer || analysis.disclaimer || confluenceAI.disclaimer || document.getElementById('riskDisclaimer')?.textContent || '');
        if (mtfConfluence) {
            this.setText(
                'mtfConfluence',
                `${mtfConfluence.dominant_direction} ${mtfConfluence.confirmed_timeframes}/${mtfConfluence.required_confirmations} · ${mtfConfluence.average_strength}%`
            );
        }

        const levels = analysis.levels || {};
        this.setText('levelEntrada', this.formatPrice(institutionalRisk.entry ?? operationalSignal.entry_aggressive ?? levels.entrada));
        this.setText('levelEntradaConservadora', this.formatPrice(operationalSignal.entry_conservative));
        this.setText('levelStop', this.formatPrice(institutionalRisk.stop_loss ?? institutionalRisk.stop ?? operationalSignal.stop_loss ?? levels.stop_loss));
        this.setText('levelTarget1', this.formatPrice(institutionalRisk.take_partial ?? institutionalRisk.take_profit_partial ?? institutionalRisk.take_profit_1 ?? operationalSignal.take_profit_1 ?? levels.alvo_1));
        this.setText('levelTarget2', this.formatPrice(institutionalRisk.take_profit ?? institutionalRisk.take_profit_2 ?? operationalSignal.take_profit_2 ?? levels.alvo_2));
        this.setText('riskRatio', Number.isFinite(Number(institutionalRisk.risk_reward ?? operationalSignal.risk_reward ?? levels.risco_retorno)) ? `1:${Number(institutionalRisk.risk_reward ?? operationalSignal.risk_reward ?? levels.risco_retorno).toFixed(2)}` : '--');
        this.setText('cancelScenario', institutionalRisk.invalidation ? `Invalida em ${this.formatPrice(institutionalRisk.invalidation)}` : operationalSignal.cancellation_scenario || '--');

        this.setText('rsiValue', this.formatNumber(indicators.rsi, 2));
        this.setText('macdValue', this.formatNumber(indicators.macd, 4));
        this.setText('atrValue', this.formatNumber(indicators.atr, 2));
        this.setText('volumeValue', this.formatCompact(indicators.volume));
        this.setText('vwapValue', this.formatPrice(indicators.vwap));
        this.setText('emaValue', `${this.formatPrice(indicators.ema9)} / ${this.formatPrice(indicators.ema21)}`);
        this.setText('bbValue', `${this.formatPrice(indicators.bollinger_lower)} - ${this.formatPrice(indicators.bollinger_upper)}`);

        this.updateReasoning(institutionalDecision.confirmations || operationalSignal.confirmations || confluenceAI.confirmations || finalScore.technical_reasons || analysis.reasoning || []);
        if (marketMessage) this.pushSoftMessage(marketMessage);
        this.updateInvalidations(institutionalDecision.invalidations || operationalSignal.invalidations || confluenceAI.invalidations || finalScore.invalidation_reasons || []);
        this.updateSupportResistance(Array.isArray(analysis.support_resistance) ? analysis.support_resistance : [], analysis.current_price || 0);
        this.updateCandleReading(Array.isArray(analysis.candle_reading) ? analysis.candle_reading : []);
        this.updateInstitutionalPanels(analysis);
    }

    deriveFinalSignalDecision(analysis, signal, fallbackScore) {
        const cardsDecision = analysis.signal_cards || {};
        if (cardsDecision.active && cardsDecision.label) {
            return {
                key: cardsDecision.active,
                label: cardsDecision.label,
                confidence: Number(cardsDecision.confidence ?? cardsDecision.score ?? fallbackScore ?? 0),
                score: Number(cardsDecision.score ?? fallbackScore ?? 0),
                intensity: cardsDecision.intensity || 'moderada',
                reason: cardsDecision.reason || '',
                cards: cardsDecision.cards || {},
                forces: cardsDecision.forces || {},
            };
        }

        const operationalSignal = analysis.operational_signal || {};
        const finalScore = analysis.final_score || {};
        const confluenceAI = analysis.confluence_ai || {};
        const advanced = analysis.advanced_confluence || {};
        const smc = analysis.smc || {};
        const volume = analysis.volume_analysis || {};
        const wyckoff = analysis.wyckoff || {};
        const elliott = analysis.elliott_wave || {};
        const tape = analysis.tape_reading || {};
        const mtf = analysis.multi_timeframe?.confluence || {};
        const validation = analysis.validation || {};
        const state = analysis.operational_state || {};
        const levels = analysis.levels || {};

        const score = Number(advanced.score ?? operationalSignal.score ?? confluenceAI.score ?? analysis.operational_score ?? fallbackScore ?? 0);
        const confidence = Number(operationalSignal.confidence ?? confluenceAI.confidence ?? finalScore.confidence ?? signal.confidence ?? score ?? 0);
        const rr = Number(operationalSignal.risk_reward ?? levels.risco_retorno ?? 0);
        const rawSignals = [
            operationalSignal.signal,
            analysis.final_signal,
            analysis.market_bias,
            confluenceAI.signal,
            finalScore.signal,
            this.getSignalText(signal.signal_type),
            mtf.dominant_direction,
        ].map((item) => String(item || '').toUpperCase());

        let bullish = 0;
        let bearish = 0;
        let waitingPressure = 0;

        rawSignals.forEach((item) => {
            if (['COMPRA', 'BUY', 'BULLISH'].includes(item)) bullish += 2;
            if (['VENDA', 'SELL', 'BEARISH'].includes(item)) bearish += 2;
            if (item.includes('AGUARDAR') || item.includes('WAIT')) waitingPressure += 2;
        });

        if (smc.institutional_bias === 'bullish' || smc.confirmed && rawSignals.includes('BUY')) bullish += 2;
        if (smc.institutional_bias === 'bearish' || smc.confirmed && rawSignals.includes('SELL')) bearish += 2;
        if (smc.has_bos && smc.structure?.trend === 'bullish') bullish += 1;
        if (smc.has_bos && smc.structure?.trend === 'bearish') bearish += 1;
        if (volume.signal === 'BULLISH_VOLUME' || volume.dominant_side === 'BUYERS') bullish += 1;
        if (volume.signal === 'BEARISH_VOLUME' || volume.dominant_side === 'SELLERS') bearish += 1;
        if (tape.order_flow_bias === 'BUY_FLOW') bullish += 2;
        if (tape.order_flow_bias === 'SELL_FLOW') bearish += 2;
        if (wyckoff.wyckoff_phase === 'acumulacao' || wyckoff.spring) bullish += 1;
        if (wyckoff.wyckoff_phase === 'distribuicao' || wyckoff.upthrust) bearish += 1;
        if (elliott.wave_bias === 'bullish' && elliott.impulse_structure?.detected) bullish += 1;
        if (elliott.wave_bias === 'bearish' && elliott.impulse_structure?.detected) bearish += 1;
        if (mtf.dominant_direction === 'BULLISH' && mtf.confirmed_timeframes >= 3) bullish += 2;
        if (mtf.dominant_direction === 'BEARISH' && mtf.confirmed_timeframes >= 3) bearish += 2;

        const invalidated = state.state === 'invalidated'
            || validation.entry_quality?.invalidated
            || smc.invalidated
            || smc.false_breakout?.detected
            || (rr > 0 && rr < 1);
        const weakContext = state.state === 'loading'
            || state.ready === false
            || state.state === 'waiting_confirmation'
            || validation.lateralization?.detected
            || volume.signal === 'NEUTRAL_VOLUME'
            || tape.order_flow_bias === 'BALANCED_FLOW'
            || !mtf.strong_signal_allowed
            || waitingPressure > 0;
        const conflict = bullish > 0 && bearish > 0 && Math.abs(bullish - bearish) <= 2;
        const dominant = bullish > bearish ? 'COMPRA' : bearish > bullish ? 'VENDA' : 'NEUTRO';
        const dominantVotes = Math.max(bullish, bearish);

        if (!analysis.success || state.state === 'loading') {
            return { key: 'wait', label: 'AGUARDAR CONFIRMACAO', confidence: Math.max(confidence, 35), score, intensity: 'carregando' };
        }
        if (score < 35 && dominantVotes < 4) {
            return { key: 'neutral', label: 'NEUTRO', confidence: Math.max(confidence, score), score, intensity: 'baixa' };
        }
        if (invalidated || conflict || weakContext || dominantVotes < 4 || score < 55) {
            return { key: 'wait', label: 'AGUARDAR CONFIRMACAO', confidence: Math.max(confidence, score), score, intensity: conflict ? 'conflito' : 'moderada' };
        }
        if (dominant === 'COMPRA') {
            return { key: 'buy', label: 'COMPRA', confidence: Math.max(confidence, score), score, intensity: score >= 75 ? 'forte' : 'moderada' };
        }
        if (dominant === 'VENDA') {
            return { key: 'sell', label: 'VENDA', confidence: Math.max(confidence, score), score, intensity: score >= 75 ? 'forte' : 'moderada' };
        }
        return { key: 'neutral', label: 'NEUTRO', confidence: Math.max(confidence, score), score, intensity: 'baixa' };
    }

    setSignalVisualState(decision) {
        const key = decision?.key || 'neutral';
        const displaySignal = decision?.label || 'NEUTRO';
        const confidenceText = Number.isFinite(Number(decision?.confidence))
            ? `${Math.round(Number(decision.confidence))}%`
            : 'ATIVO';
        const scoreText = Number.isFinite(Number(decision?.score))
            ? `S${Math.round(Number(decision.score))}`
            : '';
        const scoreLabel = scoreText ? `${confidenceText} · ${scoreText}` : confidenceText;

        const mainSignal = document.getElementById('mainSignal');
        if (mainSignal) {
            mainSignal.dataset.signal = displaySignal;
        }

        const cards = [
            { id: 'buyCardState', key: 'buy' },
            { id: 'sellCardState', key: 'sell' },
            { id: 'neutralCardState', key: 'neutral' },
            { id: 'waitCardState', key: 'wait' },
        ];
        cards.forEach((item) => {
            const cardData = decision?.cards?.[item.key] || {};
            const force = Number(cardData.force ?? decision?.forces?.[item.key]);
            const value = Number.isFinite(force)
                ? `${Math.round(force)}%${item.key === key ? ' ATIVO' : ''}`
                : item.key === key ? scoreLabel : '--';
            this.setText(item.id, value);
            const el = document.getElementById(item.id);
            const card = el?.closest('.signal-pill');
            if (!card) return;
            card.classList.toggle('active', item.key === key);
            card.dataset.active = item.key === key ? 'true' : 'false';
            card.dataset.intensity = item.key === key ? (decision?.intensity || 'moderada') : (Number.isFinite(force) && force >= 55 ? 'moderada' : '');
            card.title = cardData.reason || (item.key === key ? (decision?.reason || '') : `${Math.round(force || 0)}% de forca institucional`);
        });
    }

    scheduleRealtimeAnalysis() {
        clearTimeout(this.realtimeAnalysisTimer);
        this.realtimeAnalysisTimer = setTimeout(() => this.refreshAnalysisOnly(), 500);
    }

    async refreshAnalysisOnly() {
        try {
            this.marketDataEngine?.invalidate(`analysis:${this.currentAsset}:${this.currentTimeframe}`);
            const analysis = await this.fetchAnalysis(this.currentAsset, this.currentTimeframe, undefined, true);
            if (analysis?.success) this.updateAnalysisPanel(analysis, { ticker: analysis.ticker || {}, streaming: this.latestStreaming });
        } catch (error) {
            // Mantem a ultima decisao visual quando a atualizacao em tempo real falhar.
        }
    }

    updateInstitutionalPanels(analysis) {
        const smc = analysis.smc || {};
        const wyckoff = analysis.wyckoff || {};
        const context = analysis.institutional_context || {};
        const structure = smc.structure || {};
        const validation = analysis.validation || {};
        const quality = validation.entry_quality || {};
        const scenario = analysis.scenario || {};
        const falseBreakout = context.false_breakout || smc.false_breakout || {};

        this.setText('entryQuality', quality.quality || '--');
        this.setText('probabilityScore', quality.probability ? `${quality.probability}%` : '--');
        this.setText('scenarioAction', scenario.action || '--');
        this.setText('invalidatedState', quality.invalidated ? 'SIM' : 'NAO');
        this.setText('institutionalSmcScore', `${context.smc_score ?? smc.smc_score ?? '--'}`);
        this.setText('institutionalWyckoffPhase', context.wyckoff_phase || wyckoff.phase || '--');
        this.setText('institutionalBias', context.institutional_bias || smc.institutional_bias || '--');
        this.setText('institutionalBreakout', falseBreakout.detected ? `FALSO ${falseBreakout.direction || ''}` : 'REAL/NAO CONFIRMADO');
        this.setText('institutionalExplanation', context.explanation || smc.explanation || wyckoff.explanation || '--');
        this.setText('smcBos', structure.bos || '--');
        this.setText('smcChoch', structure.choch || '--');
        this.setText('smcLiquidityZone', this.formatSmartMoneyZone(context.liquidity_zone || smc.liquidity_zone));
        this.setText('smcNearestOb', this.formatSmartMoneyZone(context.relevant_order_block || smc.relevant_order_block || smc.nearest_order_block));
        this.setText('smcRelevantFvg', this.formatSmartMoneyZone(context.relevant_fvg || smc.relevant_fvg));
        this.setText('smcConfirmed', smc.confirmed ? 'SIM' : 'NAO');
        this.setText('smcInvalidated', smc.invalidated ? 'SIM' : 'NAO');
        this.setText('smcSweep', smc.liquidity_sweep?.detected ? smc.liquidity_sweep.side : 'NAO');
        this.setText('lateralState', validation.lateralization?.detected ? 'SIM' : 'NAO');
        this.updateWyckoffPanel(wyckoff);
        this.updateVolumeInstitutionalPanel(analysis.volume_analysis || {});
        this.updateAdvancedReadingsPanel(analysis);
        this.setOperationalState(analysis.operational_state || {});
    }

    pushSoftMessage(message) {
        const list = document.getElementById('reasoningList');
        if (!list || !message) return;
        const item = document.createElement('div');
        item.className = 'reasoning-item';
        item.innerHTML = `<i class="fas fa-info-circle"></i><span>${message}</span>`;
        list.prepend(item);
        while (list.children.length > 12) list.lastElementChild.remove();
    }

    updateWyckoffPanel(wyckoff) {
        this.setText('wyckoffPhase', wyckoff.phase || '--');
        this.setText('wyckoffBias', wyckoff.bias || '--');
        this.setText('wyckoffAccumulation', wyckoff.accumulation ? 'SIM' : 'NAO');
        this.setText('wyckoffDistribution', wyckoff.distribution ? 'SIM' : 'NAO');
        this.setText('wyckoffSpring', wyckoff.spring ? 'SIM' : 'NAO');
        this.setText('wyckoffUpthrust', wyckoff.upthrust ? 'SIM' : 'NAO');
        this.setText('wyckoffSellingClimax', wyckoff.selling_climax ? 'SIM' : 'NAO');
        this.setText('wyckoffBuyingClimax', wyckoff.buying_climax ? 'SIM' : 'NAO');
        this.setText('wyckoffTest', wyckoff.test ? 'SIM' : 'NAO');
        this.setText('wyckoffVolumeRatio', wyckoff.volume_ratio ? `${wyckoff.volume_ratio}x` : '--');
    }

    updateAdvancedReadingsPanel(analysis) {
        const wyckoff = analysis.wyckoff || {};
        const elliott = analysis.elliott_wave || {};
        const tape = analysis.tape_reading || {};
        const advanced = analysis.advanced_confluence || {};

        this.setText('advancedWyckoffPhase', wyckoff.wyckoff_phase || wyckoff.phase || '--');
        this.setText('advancedManipulation', wyckoff.institutional_manipulation ? 'SIM' : 'NAO');
        this.setText('advancedCurrentWave', elliott.current_wave || '--');
        this.setText('advancedWaveBias', elliott.wave_bias || '--');
        this.setText('advancedFlowBias', tape.order_flow_bias || '--');
        this.setText('advancedBuyAggression', Number.isFinite(Number(tape.buy_aggression)) ? `${Math.round(Number(tape.buy_aggression))}%` : '--');
        this.setText('advancedSellAggression', Number.isFinite(Number(tape.sell_aggression)) ? `${Math.round(Number(tape.sell_aggression))}%` : '--');
        this.setText('advancedAbsorption', tape.absorption?.detected ? 'SIM' : 'NAO');
        this.setText('advancedScore', Number.isFinite(Number(advanced.score)) ? `${Math.round(Number(advanced.score))}/100` : '--');
        this.setText('advancedExplanation', advanced.explanation || tape.explanation || elliott.explanation || wyckoff.explanation || '--');
    }

    setOperationalState(state) {
        const previousState = this.operationalState;
        const currentState = state.state || 'waiting_confirmation';
        const messages = {
            loading: 'Carregando candles e recalculando a IA...',
            neutral: 'Cenario neutro / sem entrada no momento.',
            waiting_confirmation: 'Aguardar confirmacao.',
            invalidated: 'Cenario invalidado por fator tecnico forte.',
            confirmed: 'Sinal confirmado.',
        };
        const message = state.message || messages[currentState] || messages.waiting_confirmation;

        this.setText('scenarioAction', message);
        this.setText('invalidatedState', currentState === 'invalidated' ? 'SIM' : 'NAO');

        const scoreText = document.getElementById('scoreText');
        if (scoreText) {
            scoreText.textContent = message;
            scoreText.className = `score-text state-${currentState}`;
        }

        const mainSignal = document.getElementById('mainSignal');
        if (mainSignal) {
            mainSignal.dataset.state = currentState;
        }

        this.operationalState = currentState;

        if (currentState === 'invalidated') {
            const reasons = state.invalidation_reasons || [];
            const signature = reasons.join('|') || message;
            const now = Date.now();
            const shouldToast = previousState !== 'loading'
                && (this.lastInvalidationToast.signature !== signature || now - this.lastInvalidationToast.time > 60000);
            if (shouldToast) {
                this.lastInvalidationToast = { signature, time: now };
                this.showNotification(reasons[0] || message, 'error');
            }
        }
    }

    updateVolumeInstitutionalPanel(volume) {
        this.setText('volumeSignal', volume.signal || '--');
        this.setText('volumeDominantSide', volume.dominant_side || '--');
        this.setText('volumeAboveAverage', volume.volume_above_average ? 'SIM' : 'NAO');
        this.setText('volumeAbnormal', volume.abnormal_volume ? 'SIM' : 'NAO');
        this.setText('volumeExhaustion', volume.exhaustion?.detected ? volume.exhaustion.side : 'NAO');
        this.setText('volumeAbsorption', volume.absorption?.detected ? volume.absorption.side : 'NAO');
        this.setText('volumeBreakout', volume.breakout_confirmation?.confirmed ? volume.breakout_confirmation.direction : 'NAO');
        this.setText('volumeDivergence', volume.price_volume_divergence?.detected ? volume.price_volume_divergence.type : 'NAO');
    }

    formatSmartMoneyZone(zone) {
        if (!zone) return '--';
        const label = zone.kind || zone.type || 'zona';
        const value = this.zonePrice(zone);
        return `${label} ${this.formatPrice(value)}`;
    }

    zonePrice(zone) {
        if (!zone) return NaN;
        return Number(zone.mid ?? zone.price ?? zone.high ?? zone.low);
    }

    updateGauge(score) {
        const gauge = document.querySelector('.gauge-fill');
        if (!gauge) return;
        const circumference = 282;
        const filled = Math.max(0, Math.min(100, score)) / 100 * circumference;
        gauge.setAttribute('stroke-dasharray', `${filled} ${circumference}`);
        gauge.style.stroke = score > 70 ? '#22c55e' : score > 50 ? '#facc15' : '#ef4444';
    }

    updateReasoning(reasoning) {
        const list = document.getElementById('reasoningList');
        if (!list) return;
        list.innerHTML = '';
        const items = reasoning.length ? reasoning : ['Sem motivo tecnico dominante.'];
        items.forEach((text) => {
            const item = document.createElement('div');
            item.className = 'reasoning-item';
            item.innerHTML = `<i class="fas fa-check-circle"></i><span>${text}</span>`;
            list.appendChild(item);
        });
    }

    updateInvalidations(invalidations) {
        const list = document.getElementById('invalidationList');
        if (!list) return;
        list.innerHTML = '';
        const items = invalidations.length ? invalidations : ['Sem invalidacao critica.'];
        items.forEach((text) => {
            const item = document.createElement('div');
            item.className = 'reasoning-item';
            item.innerHTML = `<i class="fas fa-times-circle"></i><span>${text}</span>`;
            list.appendChild(item);
        });
    }

    updateSupportResistance(levels, currentPrice) {
        const list = document.getElementById('srList');
        if (!list) return;
        list.innerHTML = '';
        levels.forEach((level, index) => {
            const distance = ((level.price - currentPrice) / currentPrice * 100).toFixed(2);
            const item = document.createElement('div');
            item.className = `sr-item ${level.type}`;
            item.innerHTML = `
                <span class="sr-label">${level.type === 'resistance' ? 'Resistencia' : 'Suporte'} ${index + 1}</span>
                <span class="sr-price">${this.formatPrice(level.price)}</span>
                <span class="sr-distance">${distance}%</span>
            `;
            list.appendChild(item);
        });
    }

    updateCandleReading(candles) {
        const list = document.getElementById('candleReadingList');
        if (!list) return;
        list.innerHTML = '';
        candles.forEach((candle) => {
            const row = document.createElement('div');
            row.className = `candle-row ${candle.direction}`;
            row.innerHTML = `
                <span>${candle.direction.toUpperCase()}</span>
                <span>${this.formatPrice(candle.close)}</span>
                <span>${candle.body_pct.toFixed(2)}%</span>
            `;
            list.appendChild(row);
        });
    }

    async updateMultiTimeframe() {
        const response = await fetch(`/api/multi-timeframe/${this.currentAsset}`);
        const data = await response.json();
        if (!data.success) return;
        Object.entries(data.analysis).forEach(([timeframe, item]) => {
            this.setText(`tf${timeframe.replace(/\W/g, '')}`, `${this.getDirectionText(item.direction)} ${item.strength}%`);
        });
        if (data.confluence) {
            this.setText(
                'mtfConfluence',
                `${data.confluence.dominant_direction} ${data.confluence.confirmed_timeframes}/${data.confluence.required_confirmations} · ${data.confluence.average_strength}%`
            );
        }
    }

    async updateHeatmap() {
        const response = await fetch('/api/heatmap');
        const data = await response.json();
        if (!data.success) return;
        this.renderHeatmap(data.heatmap);
    }

    renderHeatmap(heatmap) {
        const container = document.querySelector('.heatmap-grid');
        if (!container) return;
        container.innerHTML = '';

        Object.entries(heatmap).forEach(([asset, timeframes]) => {
            const row = document.createElement('div');
            row.className = 'heatmap-row';
            row.innerHTML = `<div class="heatmap-asset">${asset}</div>`;
            Object.entries(timeframes).forEach(([tf, item]) => {
                if (tf === 'confluence') return;
                const cell = document.createElement('button');
                cell.className = 'heatmap-cell';
                cell.style.backgroundColor = item.color;
                cell.innerHTML = `<span>${tf}</span><strong>${this.getDirectionText(item.direction)}</strong><small>${item.strength}%</small>`;
                cell.title = `${asset} ${tf} · ${item.trend} · ${item.signal}`;
                cell.addEventListener('click', () => {
                    this.currentAsset = asset;
                    this.currentTimeframe = tf;
                    document.getElementById('assetSelect').value = asset;
                    document.querySelectorAll('.tf-btn').forEach((btn) => {
                        btn.classList.toggle('active', btn.dataset.tf === tf);
                    });
                    this.updateDashboard(true);
                });
                row.appendChild(cell);
            });
            const confluence = timeframes.confluence || {};
            const confluenceCell = document.createElement('div');
            confluenceCell.className = 'heatmap-confluence';
            confluenceCell.textContent = `${confluence.dominant_direction || '--'} ${confluence.confirmed_timeframes || 0}/${confluence.required_confirmations || 3}`;
            row.appendChild(confluenceCell);
            container.appendChild(row);
        });
    }

    async runBacktest() {
        const button = document.getElementById('btnRunBacktest');
        if (button) {
            button.textContent = 'Executando...';
            button.disabled = true;
        }
        try {
            const response = await fetch(`/api/backtest/${this.currentAsset}?timeframe=${this.currentTimeframe}`);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Erro no backtest');
            const result = data.backtest;
            this.setText('totalTrades', result.total_trades);
            this.setText('winRate', `${result.win_rate.toFixed(1)}%`);
            this.setText('totalReturn', `${result.total_return.toFixed(2)}%`);
            this.setText('profitFactor', Number(result.profit_factor).toFixed(2));
            this.setText('maxDrawdown', `${result.max_drawdown.toFixed(2)}%`);
            this.setText('patternLearning', result.pattern_learning?.bias || '--');
            this.renderEquityCurve(result.equity_curve || []);
            this.showNotification('Backtest atualizado com dados reais da Binance.', 'success');
        } catch (error) {
            this.showNotification(error.message, 'error');
        } finally {
            if (button) {
                button.textContent = 'Executar Backtest';
                button.disabled = false;
            }
        }
    }

    renderEquityCurve(points) {
        const container = document.getElementById('equityCurve');
        if (!container || !window.LightweightCharts) return;
        if (!this.equityChart) {
            this.equityChart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: 150,
                layout: { background: { type: 'solid', color: '#05070d' }, textColor: '#94a3b8' },
                grid: { horzLines: { color: 'rgba(148,163,184,.08)' }, vertLines: { color: 'rgba(148,163,184,.05)' } },
                rightPriceScale: { borderVisible: false },
                timeScale: { borderVisible: false, timeVisible: true },
            });
            this.equitySeries = this.equityChart.addAreaSeries({
                topColor: 'rgba(56, 189, 248, 0.35)',
                bottomColor: 'rgba(56, 189, 248, 0.02)',
                lineColor: '#38bdf8',
                lineWidth: 2,
            });
        }
        this.equityChart.applyOptions({ width: container.clientWidth });
        this.equitySeries.setData(points.map((point) => ({ time: point.time, value: point.value })));
        this.equityChart.timeScale().fitContent();
    }

    async loadWatchlist() {
        const response = await fetch('/api/watchlist');
        const data = await response.json();
        if (!data.success) return;
        const container = document.getElementById('watchlist');
        if (!container) return;
        container.innerHTML = '';
        data.watchlist.forEach((symbol) => {
            const row = document.createElement('button');
            row.className = 'watch-row';
            row.innerHTML = `<strong>${symbol}</strong><span>Abrir</span>`;
            row.addEventListener('click', () => {
                this.currentAsset = symbol;
                document.getElementById('assetSelect').value = symbol;
                this.updateDashboard(true);
            });
            container.appendChild(row);
        });
    }

    async addCurrentToWatchlist() {
        await fetch('/api/watchlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: this.currentAsset }),
        });
        await this.loadWatchlist();
    }

    async loadAlerts() {
        const response = await fetch('/api/alerts');
        const data = await response.json();
        if (!data.success) return;
        this.alerts = data.alerts || [];
        const container = document.getElementById('alertsList');
        if (!container) return;
        container.innerHTML = '';
        data.alerts.slice(0, 12).forEach((alert) => {
            const row = document.createElement('div');
            row.className = 'alert-row';
            row.innerHTML = `<span>${alert.symbol} ${alert.condition_type}</span><strong>${this.formatPrice(alert.target)}</strong>`;
            container.appendChild(row);
        });
    }

    async createPriceAlert() {
        const current = document.getElementById('currentPrice')?.textContent.replace(/[^0-9.]/g, '');
        const target = Number(current || 0);
        if (!target) return;
        await fetch('/api/alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: this.currentAsset, condition_type: 'price_cross', target }),
        });
        await this.loadAlerts();
        this.showNotification('Alerta local criado.', 'success');
    }

    setConnectionState(text) {
        this.setText('connectionState', text);
        this.setText('lastUpdate', new Date().toLocaleTimeString('pt-BR'));
    }

    setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    getSignalText(signal, compact = false) {
        const map = {
            entrada_agressiva: compact ? 'COMPRA+' : 'COMPRA AGRESSIVA',
            entrada_conservadora: compact ? 'COMPRA C.' : 'COMPRA CONSERVADORA',
            compra: 'COMPRA',
            venda_agressiva: compact ? 'VENDA+' : 'VENDA AGRESSIVA',
            venda: 'VENDA',
            neutro: 'NEUTRO',
        };
        return map[signal] || signal;
    }

    getDirectionText(direction) {
        const map = {
            BULLISH: 'BUY',
            BEARISH: 'SELL',
            NEUTRAL: 'NEUTRO',
        };
        return map[direction] || direction || '--';
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

    formatPrice(price) {
        const value = Number(price);
        if (!Number.isFinite(value)) return '--';
        const digits = value >= 1000 ? 2 : value >= 1 ? 4 : 6;
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value);
    }

    formatCompact(value) {
        return new Intl.NumberFormat('en-US', {
            notation: 'compact',
            maximumFractionDigits: 2,
        }).format(Number(value || 0));
    }

    formatNumber(value, digits = 2) {
        const number = Number(value);
        return Number.isFinite(number) ? number.toFixed(digits) : '--';
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `toast-notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3200);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AdvancedDashboard();
});
