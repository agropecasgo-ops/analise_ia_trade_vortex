class RealtimeSignalsPage {
    constructor() {
        this.market = 'crypto';
        this.symbol = 'BTCUSDT';
        this.timeframe = '15m';
        this.directionFilter = 'all';
        this.statusFilter = 'all';
        this.operationalMode = this.currentOperationalMode();
        this.minScore = this.thresholdForMode(this.operationalMode);
        this.operationalModeLabel = this.labelForMode(this.operationalMode);
        this.active = [];
        this.history = [];
        this.pollTimer = null;
        this.priceThrottle = 0;
        this.websocket = new window.WebSocketEngine({ provider: 'bybit', fallbackProvider: 'binance' });
        this.init();
    }

    async init() {
        this.bind();
        await this.loadAssets();
        await this.refresh();
        this.connectPriceStream();
        this.pollTimer = setInterval(() => this.refresh(false), 12000);
    }

    bind() {
        document.getElementById('signalsMarketSelect')?.addEventListener('change', async (event) => {
            this.market = event.target.value;
            await this.loadAssets();
            this.refresh();
        });
        document.getElementById('signalsAssetSelect')?.addEventListener('change', (event) => {
            this.symbol = event.target.value;
            this.refresh();
            this.connectPriceStream();
        });
        document.getElementById('signalsTimeframeSelect')?.addEventListener('change', (event) => {
            this.timeframe = event.target.value;
            this.refresh();
            this.connectPriceStream();
        });
        document.getElementById('signalsDirectionFilter')?.addEventListener('change', (event) => {
            this.directionFilter = event.target.value;
            this.render();
        });
        document.getElementById('signalsStatusFilter')?.addEventListener('change', (event) => {
            this.statusFilter = event.target.value;
            this.render();
        });
        window.FinanceOperationalMode?.onChange?.((mode) => {
            this.operationalMode = this.currentOperationalMode(mode);
            this.minScore = this.thresholdForMode(this.operationalMode);
            this.operationalModeLabel = this.labelForMode(this.operationalMode);
            this.refresh();
        });
    }

    async loadAssets() {
        const response = await fetch(`/api/assets?market=${encodeURIComponent(this.market)}`);
        const data = await response.json();
        const marketSelect = document.getElementById('signalsMarketSelect');
        const assetSelect = document.getElementById('signalsAssetSelect');
        if (!data.success || !assetSelect) return;
        if (marketSelect && Array.isArray(data.markets)) {
            marketSelect.innerHTML = data.markets.map((item) => `<option value="${item.key}">${item.label}</option>`).join('');
            marketSelect.value = this.market;
        }
        assetSelect.innerHTML = data.assets.map((item) => `<option value="${item.symbol}">${item.symbol} - ${item.name}</option>`).join('');
        if (!data.assets.some((item) => item.symbol === this.symbol)) {
            this.symbol = data.assets[0]?.symbol || 'BTCUSDT';
        }
        assetSelect.value = this.symbol;
    }

    async refresh(renderLoading = true) {
        if (renderLoading) this.setText('signalsConnection', 'Atualizando');
        this.operationalMode = this.currentOperationalMode();
        const response = await fetch(`/api/signals/realtime?symbol=${encodeURIComponent(this.symbol)}&timeframe=${encodeURIComponent(this.timeframe)}&operationalMode=${encodeURIComponent(this.operationalMode)}`);
        const data = await response.json();
        this.operationalMode = data.operationalMode || this.operationalMode;
        this.minScore = Number(data.minScore || data.signal?.minScore || this.thresholdForMode(this.operationalMode));
        this.operationalModeLabel = data.operationalModeLabel || data.signal?.operationalModeLabel || this.labelForMode(this.operationalMode);
        this.active = data.active || [];
        this.history = data.history || [];
        this.setText('signalsActiveCount', data.stats?.active_count ?? this.active.length);
        this.setText('signalsHistoryCount', data.stats?.history_count ?? this.history.length);
        this.setText('signalsConnection', data.success ? 'Online' : 'Falha');
        this.setText('signalsUpdatedAt', this.clock());
        this.render();
    }

    connectPriceStream() {
        if (!String(this.symbol).endsWith('USDT')) {
            this.setText('signalsConnection', 'REST');
            return;
        }
        this.websocket.connectKline({
            symbol: this.symbol,
            timeframe: this.timeframe,
            onState: (state) => this.setText('signalsConnection', state),
            onKline: (kline) => {
                const price = Number(kline.c);
                if (!Number.isFinite(price) || Date.now() - this.priceThrottle < 1500) return;
                this.priceThrottle = Date.now();
                this.pushPrice(price);
            },
        });
    }

    async pushPrice(price) {
        const response = await fetch('/api/signals/price-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: this.symbol, price }),
        });
        const data = await response.json();
        if (!data.success) return;
        this.active = data.active || [];
        this.history = data.history || [];
        this.render();
    }

    render() {
        this.renderGrid('signalsActiveGrid', this.filter(this.active), false);
        this.renderGrid('signalsHistoryGrid', this.filter(this.history), true);
    }

    filter(items) {
        return (items || []).filter((signal) => {
            const directionOk = this.directionFilter === 'all' || signal.direction === this.directionFilter;
            const statusOk = this.statusFilter === 'all' || signal.status === this.statusFilter;
            return directionOk && statusOk;
        });
    }

    renderGrid(id, signals, compact) {
        const grid = document.getElementById(id);
        if (!grid) return;
        if (!signals.length) {
            grid.innerHTML = `<div class="live-empty-signal">${compact ? 'Nenhum sinal finalizado.' : this.emptySignalMessage()}</div>`;
            return;
        }
        if (compact) {
            grid.classList.add('signals-history-table');
            grid.innerHTML = this.historyTable(signals);
            return;
        }
        grid.classList.remove('signals-history-table');
        grid.innerHTML = signals.map((signal) => this.card(signal, compact)).join('');
    }

    card(signal, compact) {
        const strong = Number(signal.signalStrength || 0) >= 90 ? ' high-score' : '';
        const side = signal.direction === 'BUY' ? 'buy' : 'sell';
        const reasons = (signal.reasons || []).slice(0, 3).join(' ') || '--';
        const spark = this.sparkVars(signal);
        return this.normalizeText(`
            <article class="signal-realtime-card ${side}${strong}" style="${spark}">
                <div class="signal-realtime-head">
                    <div>
                        <h4>${signal.asset || '--'} · ${signal.timeframe || '--'}</h4>
                        <small>${this.formatDate(signal.createdAt)}</small>
                    </div>
                    <span class="signal-force">${signal.signalStrength || 0}%</span>
                </div>
                <div class="signal-direction-row">
                    <strong>${signal.direction === 'BUY' ? 'COMPRA' : 'VENDA'}</strong>
                    <span>${this.escape(signal.status || '--')}</span>
                </div>
                <div class="signal-level-grid">
                    <div><span>Entrada</span><strong>${this.price(signal.entryPrice)}</strong></div>
                    <div><span>Stop</span><strong>${this.price(signal.stopLoss)}</strong></div>
                    <div><span>Alvo 1</span><strong>${this.price(signal.takeProfit1)}</strong></div>
                    <div><span>Alvo 2</span><strong>${this.price(signal.takeProfit2)}</strong></div>
                    <div><span>Alvo final</span><strong>${this.price(signal.takeProfitFinal)}</strong></div>
                    <div><span>R/R</span><strong>1:${Number(signal.riskReward || 0).toFixed(2)}</strong></div>
                </div>
                <div class="signal-be-box ${signal.breakEven?.enabled ? 'active' : ''}">
                    <span>Break Even</span>
                    <strong>${signal.breakEven?.enabled ? 'Ativado' : this.price(signal.breakEven?.triggerPrice)}</strong>
                    <small>Novo stop: ${this.price(signal.breakEven?.newStopLoss)}</small>
                </div>
                <div class="signal-layer-row">
                    <span class="${signal.layers?.macroContext ? 'on' : ''}">Macro</span>
                    <span class="${signal.layers?.marketStructure ? 'on' : ''}">Estrutura</span>
                    <span class="${signal.layers?.confirmation ? 'on' : ''}">Confirmação</span>
                    <span class="on">Score ${signal.layers?.aiScore ?? signal.signalStrength}</span>
                </div>
                ${compact ? '' : `<p>${this.escape(reasons)}</p>`}
            </article>
        `);
    }

    historyTable(signals) {
        return this.normalizeText(`
            <div class="signals-history-row header">
                <span>Data</span>
                <span>Ativo</span>
                <span>Lado</span>
                <span>Score</span>
                <span>Status</span>
            </div>
            ${signals.map((signal) => {
                const side = signal.direction === 'BUY' ? 'buy' : 'sell';
                return `
                    <div class="signals-history-row">
                        <span>${this.formatDate(signal.createdAt)}</span>
                        <span><strong>${this.escape(signal.asset || '--')}</strong><small>${this.escape(signal.timeframe || '--')}</small></span>
                        <strong class="history-side ${side}">${signal.direction === 'BUY' ? 'Buy' : 'Sell'}</strong>
                        <strong>${Number(signal.signalStrength || 0).toFixed(0)}%</strong>
                        <span class="history-status">${this.escape(signal.status || '--')}</span>
                    </div>
                `;
            }).join('')}
        `);
    }

    sparkVars(signal) {
        const seed = String(signal.asset || '').split('').reduce((total, char) => total + char.charCodeAt(0), 0);
        const strength = Number(signal.signalStrength || 0);
        return [
            `--spark-a:${14 + (seed % 16)}%`,
            `--spark-b:${38 + (Math.round(strength) % 22)}%`,
            `--spark-c:${70 + (seed % 18)}%`,
        ].join(';');
    }

    price(value) {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return '--';
        return number >= 100 ? number.toFixed(2) : number.toFixed(5);
    }

    formatDate(value) {
        const date = value ? new Date(value) : new Date();
        if (Number.isNaN(date.getTime())) return '--';
        return date.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: '2-digit' });
    }

    clock() {
        return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    currentOperationalMode(value) {
        return window.FinanceOperationalMode?.normalize
            ? window.FinanceOperationalMode.normalize(value || window.FinanceOperationalMode.get?.())
            : ['conservador', 'moderado', 'agressivo'].includes(value) ? value : 'moderado';
    }

    thresholdForMode(mode) {
        return { conservador: 80, moderado: 65, agressivo: 50 }[this.currentOperationalMode(mode)] || 65;
    }

    labelForMode(mode) {
        return { conservador: 'Conservador', moderado: 'Moderado', agressivo: 'Agressivo' }[this.currentOperationalMode(mode)] || 'Moderado';
    }

    emptySignalMessage() {
        return `Aguardando score acima de ${this.minScore} no modo ${this.operationalModeLabel}`;
    }

    setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = this.normalizeText(value ?? '--');
    }

    normalizeText(value) {
        return window.FinanceText?.normalize ? window.FinanceText.normalize(value) : value;
    }

    escape(value) {
        return window.FinanceText?.escape
            ? window.FinanceText.escape(value)
            : String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
    }
}

document.addEventListener('DOMContentLoaded', () => new RealtimeSignalsPage());
