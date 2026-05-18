(function () {
    class InstitutionalDesk {
        constructor() {
            this.assetType = 'crypto';
            this.asset = 'BTCUSDT';
            this.timeframe = '15m';
            this.operationalMode = window.FinanceOperationalMode?.get?.() || 'moderado';
            this.chartEngine = null;
            this.marketData = new window.MarketDataEngine({ provider: 'institutional', ttl: 6000 });
            this.analysisController = null;
            this.candleController = null;
            this.cache = new Map();
            this.institutionalModeEnabled = true;
            this.init();
        }

        async init() {
            this.setupChart();
            this.bindEvents();
            await this.loadAssets();
            await this.generate(true);
        }

        setupChart() {
            this.chartEngine = new window.LiveChartEngine('institutionalChart', {
                minHeight: 540,
                watermark: {
                    visible: true,
                    text: 'FinanceAI Institutional',
                    color: 'rgba(212, 175, 55, 0.12)',
                    fontSize: 28,
                },
            }).init();
        }

        bindEvents() {
            document.getElementById('institutionalAssetType')?.addEventListener('change', async (event) => {
                this.assetType = event.target.value;
                await this.loadAssets();
            });
            document.getElementById('institutionalAsset')?.addEventListener('change', (event) => {
                this.asset = event.target.value;
            });
            document.getElementById('institutionalTimeframe')?.addEventListener('change', (event) => {
                this.timeframe = event.target.value;
            });
            window.FinanceOperationalMode?.onChange?.((mode) => {
                this.operationalMode = mode;
                this.generate(true);
            });
            document.getElementById('institutionalGenerate')?.addEventListener('click', () => this.generate(true));
            document.getElementById('institutionalFitChart')?.addEventListener('click', () => this.chartEngine?.fit?.());
            document.getElementById('institutionalModeToggle')?.addEventListener('click', () => this.toggleInstitutionalMode());
            window.addEventListener('resize', () => this.chartEngine?.resize?.());
        }

        toggleInstitutionalMode() {
            this.institutionalModeEnabled = !this.institutionalModeEnabled;
            const button = document.getElementById('institutionalModeToggle');
            button?.classList.toggle('active', this.institutionalModeEnabled);
            button?.setAttribute('aria-pressed', this.institutionalModeEnabled ? 'true' : 'false');
            this.setText('institutionalModeBadge', this.institutionalModeEnabled ? 'Modo Institucional ativo' : 'Modo Institucional em leitura');
            this.generate(true);
        }

        async loadAssets() {
            try {
                const response = await fetch(`/api/assets?market=${encodeURIComponent(this.assetType)}`);
                const data = await response.json();
                const select = document.getElementById('institutionalAsset');
                if (!data.success || !select) return;
                select.innerHTML = data.assets.map((asset) => (
                    `<option value="${this.escape(asset.symbol)}">${this.escape(asset.symbol)} - ${this.escape(asset.name || asset.symbol)}</option>`
                )).join('');
                if (!data.assets.some((item) => item.symbol === this.asset)) {
                    this.asset = data.assets[0]?.symbol || 'BTCUSDT';
                }
                select.value = this.asset;
            } catch (error) {
                this.setState('ATIVOS INDISPONIVEIS', true);
            }
        }

        async generate(force = false) {
            this.asset = document.getElementById('institutionalAsset')?.value || this.asset;
            this.assetType = document.getElementById('institutionalAssetType')?.value || this.assetType;
            this.timeframe = document.getElementById('institutionalTimeframe')?.value || this.timeframe;
            this.operationalMode = window.FinanceOperationalMode?.get?.() || this.operationalMode;
            this.setLoading(true);
            this.setState('ANALISANDO', false);
            try {
                const [candles, analysis] = await Promise.all([
                    this.loadCandles(force),
                    this.loadAnalysis(force),
                ]);
                this.renderChart(candles, analysis?.institutional || {});
                this.renderAnalysis(analysis);
                this.refreshVisualIntelligence();
                this.setState(analysis?.institutional?.status || 'CONCLUIDO', false);
            } catch (error) {
                this.setState('ERRO NA ANALISE', true);
                this.renderError(error);
            } finally {
                this.setLoading(false);
            }
        }

        async loadCandles(force) {
            this.candleController?.abort();
            this.candleController = new AbortController();
            return this.marketData.candles(this.asset, this.timeframe, 260, this.candleController.signal, force);
        }

        async loadAnalysis(force) {
            this.analysisController?.abort();
            this.analysisController = new AbortController();
            const suffix = force ? `&refresh=${Date.now()}` : '';
            const url = `/api/institutional/analysis/${encodeURIComponent(this.asset)}/${encodeURIComponent(this.timeframe)}?assetType=${encodeURIComponent(this.assetType)}&operationalMode=${encodeURIComponent(this.operationalMode)}${suffix}`;
            const response = await fetch(url, { signal: this.analysisController.signal });
            return response.json();
        }

        renderChart(candlePayload, institutional) {
            const candles = Array.isArray(candlePayload?.candles) ? candlePayload.candles : [];
            const volumes = Array.isArray(candlePayload?.volumes) ? candlePayload.volumes : [];
            this.chartEngine?.setData(candles, volumes, true);
            this.chartEngine?.setIndicators?.(candlePayload?.overlays || {});
            this.chartEngine?.clearOverlays?.();
            this.chartEngine?.applyLevels?.(this.levelsFromPlan(institutional.tradePlan || {}));
            this.chartEngine?.applyZones?.(this.zonesFromLiquidity(institutional.liquidity || {}));
            this.chartEngine?.applyMarkers?.(this.markersFromAnalysis(candles, institutional));
            this.setText('institutionalChartTitle', `${this.asset} - ${this.timeframe}`);
        }

        async refreshVisualIntelligence() {
            await Promise.allSettled([
                this.loadHeatmap(),
                this.loadLiquidityMap(),
                this.loadPerformance(),
                this.loadAdaptiveStatus(),
            ]);
        }

        async loadHeatmap() {
            const url = `/api/institutional/heatmap?symbol=${encodeURIComponent(this.asset)}&market=${encodeURIComponent(this.assetType)}`;
            const response = await fetch(url);
            const data = await response.json();
            this.renderHeatmap(data);
        }

        async loadLiquidityMap() {
            const url = `/api/institutional/liquidity-map?symbol=${encodeURIComponent(this.asset)}&timeframe=${encodeURIComponent(this.timeframe)}&limit=240`;
            const response = await fetch(url);
            const data = await response.json();
            this.renderLiquidityMap(data);
            if (data?.success) {
                this.chartEngine?.applyZones?.(data.zones || []);
                this.chartEngine?.applyMarkers?.([...(data.markers || []), ...this.markersFromAnalysis(this.chartEngine?.lastCandles || [], { direction: document.querySelector('.institutional-decision-card')?.getAttribute('data-direction') })]);
            }
        }

        async loadPerformance() {
            const response = await fetch('/api/institutional/performance?limit=300');
            const data = await response.json();
            this.renderPerformance(data);
        }

        async loadAdaptiveStatus() {
            const response = await fetch('/api/institutional/adaptive-status?limit=300');
            const data = await response.json();
            this.renderAdaptiveStatus(data);
        }

        renderAnalysis(payload) {
            const data = payload?.institutional || {};
            const plan = data.tradePlan || {};
            const probabilities = data.probabilities || {};
            const directionLabel = this.directionLabel(data.direction);
            this.setText('institutionalDirection', directionLabel);
            this.setText('institutionalStatus', this.statusLabel(data.status));
            this.setText('institutionalConfidence', `${this.formatPercent(data.confidence)}`);
            this.setText('institutionalScore', this.formatScore(data.score));
            this.setText('institutionalRR', this.formatRR(plan.riskReward));
            this.setText('institutionalTiming', data.timing?.confirmed ? 'CONFIRMADO' : 'AGUARDANDO');
            this.setText('probBuy', `${this.formatPercent(probabilities.buy)}`);
            this.setText('probSell', `${this.formatPercent(probabilities.sell)}`);
            this.setText('probSideways', `${this.formatPercent(probabilities.sideways)}`);
            this.setText('planEntry', this.formatPrice(plan.entry));
            this.setText('planStop', this.formatPrice(plan.stopLoss));
            this.setText('planTp1', this.formatPrice(plan.takeProfit1));
            this.setText('planTp2', this.formatPrice(plan.takeProfit2));
            this.setText('planFinal', this.formatPrice(plan.takeProfitFinal));
            this.setText('institutionalExplanation', data.aiExplanation || 'Sem explicacao disponivel.');
            this.setText('institutionalUpdated', this.formatTime(data.createdAt));
            this.renderStructure(data.marketStructure || {});
            this.renderLiquidity(data.liquidity || {});
            this.renderNews(data.news || {});
            this.renderInstitutionalMode(payload?.institutionalMode || {}, payload?.aiNarrative || {});
            document.querySelector('.institutional-decision-card')?.setAttribute('data-direction', data.direction || 'NEUTRAL');
        }

        renderInstitutionalMode(mode, narrative) {
            const status = this.institutionalModeEnabled ? (mode.status || narrative.status || 'AGUARDAR') : 'AGUARDAR';
            const sections = narrative.sections || {};
            const card = document.getElementById('institutionalNarrativeCard');
            card?.setAttribute('data-status', status);
            this.setText('institutionalModeStatus', this.modeStatusLabel(status));
            this.setText('institutionalModeBadge', this.institutionalModeEnabled ? 'Modo Institucional ativo' : 'Modo Institucional em leitura');
            this.setText('narrativeSummary', narrative.summary || mode.reason || 'Aguardando narrativa institucional.');
            this.setText('narrativeDirection', sections.probableDirection || '--');
            this.setText('narrativeReason', sections.analysisReason || mode.reason || '--');
            this.setText('narrativeLiquidity', sections.relevantLiquidity || '--');
            this.setText('narrativeBehavior', sections.institutionalBehavior || '--');
            this.setText('narrativeRisk', sections.operationRisk || '--');
            this.setText('narrativeEntry', sections.entryCondition || '--');
            this.setText('narrativeCancel', sections.cancelCondition || '--');
        }

        renderStructure(structure) {
            const rows = [
                ['Direcao', structure.direction || 'NEUTRAL'],
                ['Valida', structure.valid ? 'SIM' : 'NAO'],
                ['BOS', this.compactObject(structure.bos)],
                ['CHOCH', this.compactObject(structure.choch)],
                ['Order block', this.compactObject(structure.orderBlock)],
                ['FVG', this.compactObject(structure.fvg)],
            ];
            this.renderRows('marketStructurePanel', rows);
        }

        renderLiquidity(liquidity) {
            const sweep = liquidity.sweep || {};
            const rows = [
                ['Sweep', sweep.detected ? `${sweep.direction || '--'} @ ${this.formatPrice(sweep.level)}` : 'NAO'],
                ['Mais proxima', this.compactObject(liquidity.nearest)],
                ['Interna', this.compactObject(liquidity.internal)],
                ['Externa', this.compactObject(liquidity.external)],
                ['Zonas', Array.isArray(liquidity.zones) ? liquidity.zones.length : 0],
            ];
            this.renderRows('liquidityPanel', rows);
        }

        renderNews(news) {
            const items = Array.isArray(news.items) ? news.items : [];
            const headline = items[0]?.title || '--';
            const rows = [
                ['Status', news.available ? 'CONECTADO' : 'NAO CONECTADO'],
                ['Impacto', news.impact || 'UNKNOWN'],
                ['Fonte', news.source || '--'],
                ['Manchete', headline],
                ['Mensagem', news.message || 'Sem calendario de noticias nesta etapa.'],
            ];
            this.renderRows('newsPanel', rows);
        }

        renderHeatmap(data) {
            this.setText('heatmapSummary', data?.summary || 'Heatmap indisponivel.');
            this.setText('heatmapStrongest', data?.strongestAsset ? `${data.strongestAsset.symbol} ${Number(data.strongestAsset.netForce || 0).toFixed(0)}` : '--');
            this.setText('heatmapWeakest', data?.weakestAsset ? `${data.weakestAsset.symbol} ${Number(data.weakestAsset.netForce || 0).toFixed(0)}` : '--');
            const grid = document.getElementById('forceHeatmapGrid');
            if (!grid) return;
            const cells = Array.isArray(data?.cells) ? data.cells : [];
            if (!cells.length) {
                grid.innerHTML = '<div class="heatmap-empty">Sem dados de forca.</div>';
                return;
            }
            grid.innerHTML = cells.map((cell) => `
                <div class="force-cell ${this.escape(String(cell.direction || 'NEUTRAL').toLowerCase())}">
                    <div><strong>${this.escape(cell.symbol)}</strong><span>${this.escape(cell.timeframe)}</span></div>
                    <b>${Number(cell.score || 0).toFixed(0)}</b>
                    <small>C ${Number(cell.buyForce || 0).toFixed(0)}% / V ${Number(cell.sellForce || 0).toFixed(0)}% / N ${Number(cell.neutralForce || 0).toFixed(0)}%</small>
                    <em>${cell.conflict?.detected ? `Conflito ${Number(cell.conflict.level || 0).toFixed(0)}%` : 'Camadas alinhadas'}</em>
                </div>
            `).join('');
        }

        renderLiquidityMap(data) {
            this.setText('liquidityMapSummary', data?.summary || 'Mapa indisponivel.');
            const list = document.getElementById('liquidityMapList');
            if (!list) return;
            const zones = Array.isArray(data?.zones) ? data.zones : [];
            if (!zones.length) {
                list.innerHTML = '<div class="heatmap-empty">Sem zonas mapeadas.</div>';
                return;
            }
            list.innerHTML = zones.slice(0, 12).map((zone) => `
                <div class="liquidity-zone-item">
                    <span style="--zone-color:${this.escape(zone.color || '#38BDF8')}"></span>
                    <div>
                        <strong>${this.escape(zone.label || zone.type || 'Zona')}</strong>
                        <small>${this.escape(zone.type || '--')} - ${this.formatPrice(zone.low)} / ${this.formatPrice(zone.high)}</small>
                    </div>
                </div>
            `).join('');
        }

        renderPerformance(data) {
            this.setText('perfWinRate', `${Number(data?.winRate || 0).toFixed(0)}%`);
            this.setText('perfPayoff', Number(data?.payoff || 0).toFixed(2));
            this.setText('perfDrawdown', `${Number(data?.drawdown?.maxDrawdownPct || 0).toFixed(2)}%`);
            this.setText('perfBreakEven', `${Number(data?.breakEvenRate || 0).toFixed(0)}%`);
            this.setText('perfAverageRR', `1:${Number(data?.averageRiskReward || 0).toFixed(2)}`);
            const report = document.getElementById('performanceReport');
            if (!report) return;
            const rows = Object.entries(data?.byAssetTimeframe || {}).slice(0, 8);
            const best = Array.isArray(data?.bestSetups) ? data.bestSetups.slice(0, 3) : [];
            const weak = Array.isArray(data?.weakestSetups) ? data.weakestSetups.slice(0, 3) : [];
            report.innerHTML = `
                <div class="learning-subtitle">Ativo / timeframe</div>
                ${rows.length ? rows.map(([key, value]) => this.learningRow(key, `${Number(value.winRate || 0).toFixed(0)}% WR - RR ${Number(value.averageRR || 0).toFixed(2)}`)).join('') : '<div class="learning-empty">Sem sinais finalizados suficientes.</div>'}
                <div class="learning-subtitle">Setups eficientes</div>
                ${best.length ? best.map((item) => this.learningRow(item.setup, `${Number(item.winRate || 0).toFixed(0)}% WR`)).join('') : '<div class="learning-empty">Aguardando amostra.</div>'}
                <div class="learning-subtitle">Setups fracos</div>
                ${weak.length ? weak.map((item) => this.learningRow(item.setup, `${Number(item.winRate || 0).toFixed(0)}% WR`)).join('') : '<div class="learning-empty">Aguardando amostra.</div>'}
            `;
        }

        renderAdaptiveStatus(data) {
            this.setText('adaptiveAggressiveness', data?.aggressiveness || '--');
            this.setText('adaptiveScore', data?.recommendedMinimumScore ?? '--');
            this.setText('adaptiveExplanation', data?.explanation || 'Aguardando historico de performance.');
            const report = document.getElementById('adaptiveReport');
            if (!report) return;
            const preferred = Array.isArray(data?.preferredAssetTimeframes) ? data.preferredAssetTimeframes.slice(0, 5) : [];
            const reduced = Array.isArray(data?.reducedAssetTimeframes) ? data.reducedAssetTimeframes.slice(0, 5) : [];
            const badHours = Array.isArray(data?.badHours) ? data.badHours.slice(0, 5) : [];
            report.innerHTML = `
                <div class="learning-subtitle">Priorizar</div>
                ${preferred.length ? preferred.map((item) => this.learningRow(item.key, `${Number(item.winRate || 0).toFixed(0)}% WR`)).join('') : '<div class="learning-empty">Sem preferencia estatistica.</div>'}
                <div class="learning-subtitle">Reduzir</div>
                ${reduced.length ? reduced.map((item) => this.learningRow(item.key, `${Number(item.winRate || 0).toFixed(0)}% WR`)).join('') : '<div class="learning-empty">Sem reducao recomendada.</div>'}
                <div class="learning-subtitle">Horarios ruins</div>
                ${badHours.length ? badHours.map((item) => this.learningRow(item.hour, `${item.losses}/${item.signals} perdas`)).join('') : '<div class="learning-empty">Nenhum horario bloqueado.</div>'}
            `;
        }

        learningRow(label, value) {
            return `<div class="learning-row"><span>${this.escape(label)}</span><strong>${this.escape(value)}</strong></div>`;
        }

        renderRows(id, rows) {
            const container = document.getElementById(id);
            if (!container) return;
            container.innerHTML = rows.map(([label, value]) => (
                `<div><span>${this.escape(label)}</span><strong>${this.escape(value ?? '--')}</strong></div>`
            )).join('');
        }

        levelsFromPlan(plan) {
            return [
                { label: 'ENTRY', price: plan.entry, color: '#38BDF8' },
                { label: 'STOP', price: plan.stopLoss, color: '#EF4444' },
                { label: 'TP1', price: plan.takeProfit1, color: '#22C55E' },
                { label: 'TP2', price: plan.takeProfit2, color: '#16A34A' },
                { label: 'FINAL', price: plan.takeProfitFinal, color: '#D4AF37' },
            ].filter((item) => Number.isFinite(Number(item.price)));
        }

        zonesFromLiquidity(liquidity) {
            const zones = [];
            const addZone = (zone, label, color) => {
                if (!zone) return;
                const price = Number(zone.price ?? zone.mid ?? zone.level);
                const low = Number(zone.low ?? price);
                const high = Number(zone.high ?? price);
                if (!Number.isFinite(low) || !Number.isFinite(high)) return;
                zones.push({
                    label,
                    type: zone.side || zone.type || 'liquidity',
                    low: Math.min(low, high),
                    high: Math.max(low, high),
                    color,
                    opacity: 0.22,
                    active: true,
                });
            };
            addZone(liquidity.nearest, 'LIQ', '#38BDF8');
            addZone(liquidity.internal, 'INT LIQ', '#D4AF37');
            addZone(liquidity.external, 'EXT LIQ', '#A78BFA');
            if (liquidity.sweep?.detected) addZone({ price: liquidity.sweep.level, side: liquidity.sweep.side }, 'SWEEP', '#F59E0B');
            return zones.slice(0, 8);
        }

        markersFromAnalysis(candles, institutional) {
            const last = Array.isArray(candles) ? candles[candles.length - 1] : null;
            if (!last) return [];
            const direction = institutional.direction || 'NEUTRAL';
            return [{
                time: last.time,
                position: direction === 'BUY' ? 'belowBar' : 'aboveBar',
                shape: direction === 'BUY' ? 'arrowUp' : direction === 'SELL' ? 'arrowDown' : 'circle',
                color: direction === 'BUY' ? '#22C55E' : direction === 'SELL' ? '#EF4444' : '#D4AF37',
                text: this.directionLabel(direction),
            }];
        }

        renderError(error) {
            this.setText('institutionalStatus', 'Nao foi possivel gerar a analise.');
            this.setText('institutionalExplanation', error?.message || 'Falha inesperada na analise institucional.');
        }

        setLoading(isLoading) {
            const button = document.getElementById('institutionalGenerate');
            if (!button) return;
            button.disabled = isLoading;
            button.classList.toggle('loading', isLoading);
            button.querySelector('span').textContent = isLoading ? 'Analisando...' : 'Gerar Analise IA';
        }

        setState(text, error) {
            this.setText('institutionalDeskState', text);
            document.getElementById('institutionalStateDot')?.classList.toggle('error', Boolean(error));
        }

        setText(id, value) {
            const element = document.getElementById(id);
            if (element) element.textContent = value ?? '--';
        }

        directionLabel(direction) {
            return { BUY: 'COMPRA', SELL: 'VENDA', NEUTRAL: 'NEUTRO' }[direction] || 'NEUTRO';
        }

        statusLabel(status) {
            return {
                HIGH_PROBABILITY: 'Alta probabilidade, com risco controlado',
                WAIT_CONFIRMATION: 'Aguardando confirmacao institucional',
                DANGEROUS_MARKET: 'Mercado perigoso',
                NO_TRADE: 'Sem trade',
            }[status] || 'Aguardando analise';
        }

        modeStatusLabel(status) {
            return {
                OPERAR: 'OPERAR',
                AGUARDAR: 'AGUARDAR',
                MERCADO_PERIGOSO: 'MERCADO PERIGOSO',
            }[status] || 'AGUARDAR';
        }

        formatPercent(value) {
            const number = Number(value);
            return Number.isFinite(number) ? `${number.toFixed(0)}%` : '--';
        }

        formatScore(value) {
            const number = Number(value);
            return Number.isFinite(number) ? `${number.toFixed(0)}/100` : '--';
        }

        formatRR(value) {
            const number = Number(value);
            return Number.isFinite(number) && number > 0 ? `1:${number.toFixed(2)}` : '--';
        }

        formatPrice(value) {
            const number = Number(value);
            if (!Number.isFinite(number) || number === 0) return '--';
            return number >= 100 ? number.toFixed(2) : number.toFixed(6);
        }

        formatTime(value) {
            const date = value ? new Date(value) : null;
            return date && Number.isFinite(date.getTime()) ? date.toLocaleString('pt-BR') : '--';
        }

        compactObject(value) {
            if (!value) return '--';
            if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value;
            const side = value.side || value.type || value.direction || value.bias || '';
            const price = value.price ?? value.level ?? value.mid;
            if (price !== undefined && price !== null) return `${side || 'zona'} @ ${this.formatPrice(price)}`;
            if (value.detected !== undefined) return value.detected ? (side || 'detectado') : 'NAO';
            return side || 'mapeado';
        }

        escape(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        window.institutionalDesk = new InstitutionalDesk();
    });
})();
