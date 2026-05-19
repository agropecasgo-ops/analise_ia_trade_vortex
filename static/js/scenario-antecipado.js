(function () {
    class ScenarioAntecipado {
        constructor() {
            this.assetType = 'crypto';
            this.asset = 'BTCUSDT';
            this.timeframe = '15m';
            this.chartEngine = null;
            this.marketData = new window.MarketDataEngine({ provider: 'institutional', ttl: 6000 });
            this.analysisController = null;
            this.candleController = null;
            this.init();
        }

        async init() {
            this.setupChart();
            this.bindEvents();
            await this.loadAssets();
            await this.generate(true);
        }

        setupChart() {
            this.chartEngine = new window.LiveChartEngine('scenarioChart', {
                minHeight: 520,
                watermark: {
                    visible: true,
                    text: 'FinanceAI Cenário Antecipado',
                    color: 'rgba(248, 113, 113, 0.14)',
                    fontSize: 24,
                },
            }).init();
        }

        bindEvents() {
            document.getElementById('scenarioAssetType')?.addEventListener('change', async (event) => {
                this.assetType = event.target.value;
                await this.loadAssets();
            });
            document.getElementById('scenarioAsset')?.addEventListener('change', (event) => {
                this.asset = event.target.value;
            });
            document.getElementById('scenarioTimeframe')?.addEventListener('change', (event) => {
                this.timeframe = event.target.value;
            });
            document.getElementById('scenarioGenerate')?.addEventListener('click', () => this.generate(true));
            window.addEventListener('resize', () => this.chartEngine?.resize?.());
        }

        async loadAssets() {
            try {
                const response = await fetch(`/api/assets?market=${encodeURIComponent(this.assetType)}`);
                const data = await response.json();
                const select = document.getElementById('scenarioAsset');
                if (!data.success || !select) return;
                select.innerHTML = data.assets.map((asset) => (
                    `<option value="${this.escape(asset.symbol)}">${this.escape(asset.symbol)} - ${this.escape(asset.name || asset.symbol)}</option>`
                )).join('');
                if (!data.assets.some((item) => item.symbol === this.asset)) {
                    this.asset = data.assets[0]?.symbol || 'BTCUSDT';
                }
                select.value = this.asset;
            } catch (error) {
                this.setHealth('ATIVOS INDISPONÍVEIS', true);
            }
        }

        async generate(force = false) {
            this.asset = document.getElementById('scenarioAsset')?.value || this.asset;
            this.assetType = document.getElementById('scenarioAssetType')?.value || this.assetType;
            this.timeframe = document.getElementById('scenarioTimeframe')?.value || this.timeframe;
            this.setHealth('ANALISANDO', false);
            this.setLoading(true);
            try {
                const [candles, analysis] = await Promise.all([
                    this.loadCandles(force),
                    this.loadAnalysis(force),
                ]);
                this.renderChart(candles, analysis?.institutional || {});
                this.renderScenario(analysis?.institutional || {});
                this.setHealth('CENÁRIO ATUALIZADO', false);
            } catch (error) {
                this.setHealth('FALHA NA ANÁLISE', true);
                this.renderError(error);
            } finally {
                this.setLoading(false);
            }
        }

        async loadCandles(force) {
            this.candleController?.abort();
            this.candleController = new AbortController();
            return this.marketData.candles(this.asset, this.timeframe, 320, this.candleController.signal, force);
        }

        async loadAnalysis(force) {
            this.analysisController?.abort();
            this.analysisController = new AbortController();
            const suffix = force ? `&refresh=${Date.now()}` : '';
            const url = `/api/institutional/analysis/${encodeURIComponent(this.asset)}/${encodeURIComponent(this.timeframe)}?assetType=${encodeURIComponent(this.assetType)}&operationalMode=moderado${suffix}`;
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
            this.chartEngine?.applyMarkers?.(this.markersFromPlan(institutional.tradePlan || {}, institutional));
            this.setText('scenarioChartTitle', `${this.asset} · ${this.timeframe}`);
        }

        renderScenario(institutional) {
            const plan = institutional.tradePlan || {};
            const risk = institutional.risk || {};
            const status = institutional.status || 'WAIT_CONFIRMATION';
            const entryStatus = institutional.entryStatus || institutional.entryTiming?.label || '';
            const warning = this.buildWarning(status, entryStatus, institutional);
            const riskReward = plan.riskReward ?? risk.riskReward ?? '--';

            this.setText('scenarioDirection', this.directionLabel(institutional.direction));
            this.setText('scenarioStatus', this.statusLabel(status));
            this.setText('scenarioRisk', this.formatRR(riskReward));
            this.setText('scenarioEntry', this.formatPrice(plan.entry));
            this.setText('scenarioStop', this.formatPrice(plan.stopLoss));
            this.setText('scenarioTp1', this.formatPrice(plan.takeProfit1));
            this.setText('scenarioTp2', this.formatPrice(plan.takeProfit2));
            this.setText('scenarioWarning', warning || 'Nenhum alerta de perseguição no momento.');
            this.setText('scenarioExplanation', institutional.aiExplanation || institutional.explanation || 'Sem análise textual disponível.');
            this.renderScenarioDetails(institutional, status, entryStatus);
        }

        renderScenarioDetails(institutional, status, entryStatus) {
            const structure = institutional.marketStructure || {};
            const liquidity = institutional.liquidity || {};
            const details = [
                ['SMC', institutional.institutionalBehavior?.smartMoneyBias || 'N/A'],
                ['BOS', this.compactObject(structure.bos)],
                ['CHOCH', this.compactObject(structure.choch)],
                ['POC / Volume Profile', this.compactObject(liquidity.nearest)],
                ['Sweep', this.compactObject(liquidity.sweep)],
                ['Zona de defesa', this.compactObject(liquidity.internal)],
                ['Invalidação', institutional.risk?.rejections?.[0] || institutional.risk?.invalidations?.[0] || 'N/A'],
                ['Entrada ideal', entryStatus || 'N/A'],
                ['Macro H1/M15', institutional.macroContext?.summary || 'N/A'],
            ];
            const container = document.getElementById('scenarioDetails');
            if (!container) return;
            container.innerHTML = details.map(([label, value]) => (
                `<div class="scenario-detail-item"><span>${this.escape(label)}</span><strong>${this.escape(value ?? '--')}</strong></div>`
            )).join('');
        }

        buildWarning(status, entryStatus, institutional) {
            const lower = String(entryStatus || '').toLowerCase();
            if (status === 'ENTRY_LATE' || lower.includes('tarde') || status === 'NO_ENTRY') {
                return 'Entrada atrasada ou inválida: não perseguir preço.';
            }
            if (status === 'DANGEROUS_MARKET' || institutional.institutionalBehavior?.falseBreakout?.detected) {
                return 'Mercado perigoso: evite entrada agressiva.';
            }
            if (status === 'ENTRY_EARLY') {
                return 'Entrada antecipada: observe o gatilho e mantenha disciplina.';
            }
            return '';
        }

        levelsFromPlan(plan) {
            return [
                { label: 'ENTRADA', price: plan.entry, color: '#38BDF8' },
                { label: 'STOP', price: plan.stopLoss, color: '#EF4444' },
                { label: 'TP1', price: plan.takeProfit1, color: '#22C55E' },
                { label: 'TP2', price: plan.takeProfit2, color: '#16A34A' },
            ].filter((item) => Number.isFinite(Number(item.price)));
        }

        zonesFromLiquidity(liquidity) {
            const zones = [];
            const add = (zone, label, color) => {
                const low = Number(zone?.low ?? zone?.price ?? zone?.level);
                const high = Number(zone?.high ?? zone?.price ?? zone?.level);
                if (!Number.isFinite(low) || !Number.isFinite(high)) return;
                zones.push({ label, low: Math.min(low, high), high: Math.max(low, high), color, opacity: 0.16, active: true });
            };
            add(liquidity.nearest, 'POC', '#38BDF8');
            add(liquidity.internal, 'DEFESA', '#F9A8D4');
            add(liquidity.external, 'LIQUIDEZ', '#A78BFA');
            if (liquidity.sweep?.detected) {
                add({ low: liquidity.sweep.level, high: liquidity.sweep.level }, 'SWEEP', '#FBBF24');
            }
            return zones;
        }

        markersFromPlan(plan, institutional) {
            const markers = [];
            const time = institutional.createdAt || Date.now();
            if (Number.isFinite(Number(plan.entry))) {
                markers.push({ time, position: 'belowBar', color: '#38BDF8', shape: 'arrowUp', text: 'Entrada', price: plan.entry });
            }
            if (Number.isFinite(Number(plan.stopLoss))) {
                markers.push({ time, position: 'aboveBar', color: '#EF4444', shape: 'arrowDown', text: 'Stop', price: plan.stopLoss });
            }
            if (Number.isFinite(Number(plan.takeProfit1))) {
                markers.push({ time, position: 'aboveBar', color: '#22C55E', shape: 'circle', text: 'Alvo 1', price: plan.takeProfit1 });
            }
            if (Number.isFinite(Number(plan.takeProfit2))) {
                markers.push({ time, position: 'aboveBar', color: '#16A34A', shape: 'circle', text: 'Alvo 2', price: plan.takeProfit2 });
            }
            return markers;
        }

        renderError(error) {
            this.setText('scenarioStatus', 'Erro ao gerar cenário.');
            this.setText('scenarioExplanation', error?.message || 'Falha inesperada ao carregar os dados do cenário.');
        }

        setLoading(isLoading) {
            const button = document.getElementById('scenarioGenerate');
            if (!button) return;
            button.disabled = isLoading;
            button.classList.toggle('loading', isLoading);
            button.querySelector('span').textContent = isLoading ? 'Analisando...' : 'Gerar Cenário Antecipado';
        }

        setHealth(text, error) {
            const element = document.getElementById('scenarioHealth');
            if (!element) return;
            element.textContent = text;
            element.style.background = error ? 'rgba(248, 113, 113, 0.16)' : 'rgba(34, 197, 94, 0.12)';
            element.style.color = error ? '#fecaca' : '#86efac';
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
                HIGH_PROBABILITY: 'Alta probabilidade',
                WAIT_CONFIRMATION: 'Aguardando confirmação',
                DANGEROUS_MARKET: 'Mercado perigoso',
                NO_TRADE: 'Sem trade',
                ENTRY_EARLY: 'Entrada antecipada',
                ENTRY_CONFIRMED: 'Entrada confirmada',
                ENTRY_LATE: 'Entrada atrasada',
                NO_ENTRY: 'Não entrar',
            }[status] || status || 'Aguardando análise';
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

        compactObject(value) {
            if (!value) return 'NÃO';
            if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
            const side = value.side || value.type || value.direction || value.bias || '';
            const price = value.price ?? value.level ?? value.mid;
            if (price !== undefined && price !== null) return `${side || 'zona'} @ ${this.formatPrice(price)}`;
            if (value.detected !== undefined) return value.detected ? (side || 'detected') : 'NÃO';
            return side || 'N/A';
        }

        escape(value) {
            return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        window.scenarioAntecipado = new ScenarioAntecipado();
    });
})();
