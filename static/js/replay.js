class ReplayDashboard {
    constructor() {
        this.sessionId = null;
        this.timer = null;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.currentMarket = 'crypto';
        this.mode = 'operacional';
        this.lastVoiceState = '';
        this.lastVoiceSignal = '';
        this.init();
    }

    async init() {
        this.setupChart();
        this.bindEvents();
        window.financeVoiceAssistant?.bindControls('voice');
        await this.loadAssets();
    }

    setupChart() {
        const container = document.getElementById('replayChart');
        this.chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: Math.max(container.clientHeight, 620),
            layout: { background: { type: 'solid', color: '#05070D' }, textColor: '#F8FAFC' },
            grid: { horzLines: { color: 'rgba(56,189,248,.08)' }, vertLines: { color: 'rgba(255,255,255,.035)' } },
            timeScale: { timeVisible: true, secondsVisible: false },
        });
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#22C55E', downColor: '#EF4444', borderUpColor: '#22C55E', borderDownColor: '#EF4444', wickUpColor: '#22C55E', wickDownColor: '#EF4444',
        });
        this.volumeSeries = this.chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '', scaleMargins: { top: 0.82, bottom: 0 } });
        window.addEventListener('resize', () => this.chart.applyOptions({ width: container.clientWidth }));
    }

    bindEvents() {
        document.getElementById('replayMarket')?.addEventListener('change', async (event) => {
            this.currentMarket = event.target.value;
            await this.loadAssets();
        });
        document.getElementById('replayMode')?.addEventListener('change', (event) => {
            this.mode = event.target.value;
            this.setText('replayModeTitle', this.modeLabel());
        });
        document.getElementById('replayStartBtn')?.addEventListener('click', () => this.start());
        document.getElementById('replayPauseBtn')?.addEventListener('click', () => this.pause());
        document.getElementById('replayResumeBtn')?.addEventListener('click', () => this.play());
        document.getElementById('replayNextBtn')?.addEventListener('click', () => this.step(1, true));
        document.getElementById('replayPrevBtn')?.addEventListener('click', () => this.step(-1, true));
        document.getElementById('replayResetBtn')?.addEventListener('click', () => this.reset());
    }

    async loadAssets() {
        const response = await fetch(`/api/assets?market=${encodeURIComponent(this.currentMarket)}`);
        const data = await response.json();
        const market = document.getElementById('replayMarket');
        const asset = document.getElementById('replayAsset');
        if (market && Array.isArray(data.markets)) {
            market.innerHTML = data.markets.map((item) => `<option value="${item.key}">${item.label}</option>`).join('');
            market.value = this.currentMarket;
        }
        if (asset) {
            asset.innerHTML = data.assets.map((item) => `<option value="${item.symbol}">${item.symbol} - ${item.name}</option>`).join('');
        }
    }

    async start() {
        clearInterval(this.timer);
        const payload = {
            market: document.getElementById('replayMarket').value,
            symbol: document.getElementById('replayAsset').value,
            timeframe: document.getElementById('replayTimeframe').value,
            start_date: this.dateValue('replayStart'),
            end_date: this.dateValue('replayEnd'),
            speed: Number(document.getElementById('replaySpeed').value || 1),
        };
        this.mode = document.getElementById('replayMode')?.value || this.mode;
        const data = await this.post(this.replayUrl('start'), payload);
        if (!data.success) {
            this.toast(data.message || data.error || 'Falha ao iniciar replay', 'error');
            return;
        }
        this.sessionId = data.session_id;
        this.render(data);
        this.play();
    }

    play() {
        if (!this.sessionId) return;
        clearInterval(this.timer);
        const speed = Number(document.getElementById('replaySpeed').value || 1);
        this.timer = setInterval(() => this.step(1), Math.max(120, 1000 / speed));
    }

    async pause() {
        clearInterval(this.timer);
        if (this.sessionId) this.render(await this.post(this.replayUrl('pause'), { session_id: this.sessionId }));
    }

    async reset() {
        clearInterval(this.timer);
        if (this.sessionId) this.render(await this.post(this.replayUrl('reset'), { session_id: this.sessionId }));
    }

    async step(direction = 1, manual = false) {
        if (!this.sessionId) return;
        const data = await this.post(this.replayUrl('step'), { session_id: this.sessionId, direction });
        this.render(data);
        if (manual) clearInterval(this.timer);
        if (data.finished) {
            clearInterval(this.timer);
            this.loadResults();
        }
    }

    async loadResults() {
        const response = await fetch(`/api/replay/results?session_id=${encodeURIComponent(this.sessionId)}`);
        this.renderResults(await response.json());
    }

    render(data) {
        if (!data?.success) return;
        this.candleSeries.setData(data.candles || []);
        this.volumeSeries.setData(data.mode === 'operacional' ? [] : (data.volumes || []));
        const markers = data.mode === 'operacional'
            ? (window.VisualAIOverlays?.buildOperationalMarkers(data.candles || [], data.operacional_reading || data) || [])
            : (window.VisualAIOverlays?.buildCompleteMarkers(data.candles || [], data.live_status || {}) || []);
        window.VisualAIOverlays?.set(this.candleSeries, [], markers);
        const live = data.live_status || {};
        this.mode = data.mode || this.mode;
        this.setText('replayModeTitle', this.modeLabel());
        this.setText('replayTitle', `${data.symbol} · ${data.timeframe}`);
        this.setText('replayClock', new Date((data.current_time || 0) * 1000).toLocaleString('pt-BR'));
        this.setText('replayOperationalStatus', live.status || '--');
        this.setText('replayMainMessage', live.message || '--');
        this.setText('replayScore', `${live.confluence_score ?? '--'}/100`);
        this.setText('replayConfidence', `${live.confidence ?? '--'}%`);
        this.setText('replayDirection', live.probable_direction || '--');
        this.setText('replayRiskReward', Number.isFinite(Number(live.risk_reward)) ? `1:${Number(live.risk_reward).toFixed(2)}` : '--');
        this.setText('replayAggressiveEntry', this.formatPrice(live.entry_aggressive));
        this.setText('replayConservativeEntry', this.formatPrice(live.entry_conservative));
        this.setText('replayStopLoss', this.formatPrice(live.stop_loss));
        this.setText('replayTakeProfit', this.formatPrice(live.take_profit));
        this.setText('replayReason', live.reason || '--');
        document.getElementById('replayStatusCard').dataset.state = live.state || 'ANALYZING';
        this.handleVoice(live, data.signal);
        this.setText('replayProgressText', `${data.index}/${data.total} · ${data.progress}%`);
        document.getElementById('replayProgressBar').style.width = `${data.progress}%`;
        this.renderSignals([...(data.signals || []), ...(data.history || [])]);
        this.renderResults({ stats: data.stats || {} });
    }

    renderSignals(signals) {
        const grid = document.getElementById('replaySignalsGrid');
        this.setText('replaySignalsCount', `${signals.length} sinais`);
        if (!signals.length) {
            grid.innerHTML = '<div class="live-empty-signal">Nenhum sinal gerado ainda.</div>';
            return;
        }
        grid.innerHTML = signals.slice().reverse().map((signal) => `
            <article class="live-signal-card ${String(signal.direction || '').toLowerCase()}">
                <div class="live-signal-head"><div><h4>${signal.symbol} · ${signal.timeframe}</h4><small>${new Date(signal.timestamp).toLocaleString('pt-BR')}</small></div><span class="live-signal-direction">${signal.direction}</span></div>
                <div class="live-signal-metrics"><div><span>Score</span><strong>${signal.confluence_score}/100</strong></div><div><span>Conf.</span><strong>${signal.confidence}%</strong></div><div><span>Status</span><strong>${signal.status}</strong></div></div>
                <div class="live-signal-levels"><div><span>Entrada</span><strong>${this.formatPrice(signal.entry)}</strong></div><div><span>Stop</span><strong>${this.formatPrice(signal.stop_loss)}</strong></div><div><span>TP1</span><strong>${this.formatPrice(signal.take_profit_1)}</strong></div><div><span>TP2</span><strong>${this.formatPrice(signal.take_profit_2)}</strong></div><div><span>TP3</span><strong>${this.formatPrice(signal.take_profit_3)}</strong></div><div><span>Resultado</span><strong>${signal.partial_result || '--'}</strong></div></div>
                <p class="live-signal-reason">${signal.explanation || signal.technical_reason || '--'}</p>
            </article>
        `).join('');
    }

    handleVoice(live, signal) {
        const state = live?.state || '';
        if (state && state !== this.lastVoiceState) {
            this.lastVoiceState = state;
            window.financeVoiceAssistant?.speakLiveStatus(live);
        }
        if (signal && signal.id) {
            const signature = `${signal.id}:${signal.status}:${signal.partial_result || ''}`;
            if (signature !== this.lastVoiceSignal) {
                this.lastVoiceSignal = signature;
                window.financeVoiceAssistant?.speakSignal(signal);
            }
        }
    }

    renderResults(data) {
        const stats = data.stats || {};
        const grid = document.getElementById('replayStatsGrid');
        const items = [
            ['Total de sinais', stats.total_signals], ['Acertos', stats.wins], ['Erros', stats.losses],
            ['Taxa de acerto', `${stats.win_rate || 0}%`], ['Gain medio', `${stats.average_gain || 0}%`],
            ['Loss medio', `${stats.average_loss || 0}%`], ['Profit factor', stats.profit_factor],
            ['Drawdown', `${stats.drawdown || 0}%`], ['Retorno estimado', `${stats.estimated_return || 0}%`],
        ];
        grid.innerHTML = items.map(([label, value]) => `<div class="replay-stat"><span>${label}</span><strong>${value ?? '--'}</strong></div>`).join('');
    }

    async post(url, payload) {
        const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        return response.json();
    }

    replayUrl(action) {
        return this.mode === 'operacional' ? `/api/replay/operacional/${action}` : `/api/replay/${action}`;
    }

    modeLabel() {
        return this.mode === 'operacional' ? 'Replay Operacional Leitura Grafica' : 'Replay IA Completa';
    }

    dateValue(id) {
        const value = document.getElementById(id).value;
        return value ? new Date(value).toISOString() : null;
    }

    setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value ?? '--';
    }

    formatPrice(price) {
        const value = Number(price);
        if (!Number.isFinite(value) || value === 0) return '--';
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: value >= 1 ? 4 : 6 }).format(value);
    }

    toast(message, type = 'info') {
        const el = document.createElement('div');
        el.className = `toast-notification ${type}`;
        el.textContent = message;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3200);
    }
}

document.addEventListener('DOMContentLoaded', () => new ReplayDashboard());
