(function () {
    const state = {
        symbol: 'BTCUSDT',
        timeframe: '15m',
        market: 'crypto',
        chartEngine: null,
        chart: null,
        candleSeries: null,
        controller: null,
        assetsByMarket: {},
        liveTimer: null,
    };

    const $ = (id) => document.getElementById(id);

    document.addEventListener('DOMContentLoaded', () => {
        initChart();
        bindControls();
        loadAssets().finally(refreshAll);
    });

    function bindControls() {
        $('operacionalMarket')?.addEventListener('change', (event) => {
            state.market = event.target.value;
            populateAssets(state.market);
            state.symbol = $('operacionalAsset').value;
            refreshAll();
        });
        $('operacionalAsset')?.addEventListener('change', (event) => {
            state.symbol = event.target.value;
            refreshAll();
        });
        $('operacionalTimeframe')?.addEventListener('change', (event) => {
            state.timeframe = event.target.value;
            refreshAll();
        });
        $('operacionalRefresh')?.addEventListener('click', refreshAll);
        $('opFitChart')?.addEventListener('click', () => state.chart?.timeScale().fitContent());
        window.addEventListener('resize', () => resizeChart());
    }

    async function loadAssets() {
        const response = await fetch('/api/assets');
        const data = await response.json();
        if (!data.success) return;
        const marketSelect = $('operacionalMarket');
        marketSelect.innerHTML = data.markets.map((market) => (
            `<option value="${market.key}">${market.label}</option>`
        )).join('');
        data.markets.forEach((market) => {
            state.assetsByMarket[market.key] = market.assets || [];
        });
        marketSelect.value = state.market;
        populateAssets(state.market);
    }

    function populateAssets(market) {
        const assetSelect = $('operacionalAsset');
        const assets = state.assetsByMarket[market] || [{ symbol: 'BTCUSDT', name: 'Bitcoin / USDT' }];
        assetSelect.innerHTML = assets.map((asset) => (
            `<option value="${asset.symbol}">${asset.symbol} - ${asset.name || asset.symbol}</option>`
        )).join('');
        if (!assets.some((asset) => asset.symbol === state.symbol)) {
            state.symbol = assets[0]?.symbol || 'BTCUSDT';
        }
        assetSelect.value = state.symbol;
    }

    function initChart() {
        state.chartEngine = new window.LiveChartEngine('operacionalChart', {
            minHeight: 520,
            watermark: {
                visible: true,
                text: 'Leitura Grafica Operacional',
                color: 'rgba(212, 175, 55, 0.12)',
                fontSize: 16,
                horzAlign: 'right',
                vertAlign: 'bottom',
            },
        }).init();
        state.chart = state.chartEngine?.chart;
        state.candleSeries = state.chartEngine?.candleSeries;
    }

    function resizeChart() {
        state.chartEngine?.resize();
    }

    async function refreshAll() {
        if (state.controller) state.controller.abort();
        state.controller = new AbortController();
        state.symbol = $('operacionalAsset')?.value || state.symbol;
        state.timeframe = $('operacionalTimeframe')?.value || state.timeframe;
        setLoading();
        try {
            const [candlesResponse, analysisResponse] = await Promise.all([
                fetch(`/api/operacional/candles/${state.symbol}/${state.timeframe}?limit=260`, { signal: state.controller.signal }),
                fetch(`/api/operacional/analysis/${state.symbol}/${state.timeframe}?limit=260`, { signal: state.controller.signal }),
            ]);
            const candlesData = await candlesResponse.json();
            const analysis = await analysisResponse.json();
            renderChart(candlesData);
            renderAnalysis(analysis, candlesData);
            refreshLive();
            scheduleLive();
        } catch (error) {
            if (error.name !== 'AbortError') {
                renderError(error);
            }
        }
    }

    function setLoading() {
        setText('opDominantContext', 'ANALISANDO');
        setText('opMainNarrative', 'Atualizando leitura operacional grafica...');
        setText('opChartTitle', `${state.symbol} · ${state.timeframe}`);
    }

    function renderChart(data) {
        if (!data?.candles?.length || !state.chartEngine) return;
        state.chartEngine.setData(data.candles, data.volumes || [], true);
        setText('opSymbol', data.symbol || state.symbol);
        setText('opMarket', data.market_label || data.market || '--');
        setText('opSource', data.source || '--');
        setText('opMarketStatus', statusLabel(data.market_status));
    }

    function renderAnalysis(data, candlePayload) {
        if (!data?.success) {
            renderError(new Error(data?.error || 'Leitura operacional indisponivel.'));
            return;
        }
        const opContext = data.operacional_context || {};
        const opTrend = data.operacional_trend || {};
        const opRisk = data.operacional_risk || {};
        const opSignal = data.operacional_signal || {};
        const opChart = data.operacional_chart || {};

        setText('opContext', opContext.label || '--');
        setText('opBias', opContext.directional_bias || opTrend.bias || '--');
        setText('opDominantContext', opContext.label || 'MERCADO SEM CLAREZA');
        setText('opMovementStrength', opTrend.strength_label || '--');
        setText('opQuality', `${data.operacional_score ?? opContext.quality ?? '--'}%`);
        setText('opScenarioRisk', opRisk.scenario_risk || opContext.risk || '--');
        setText('opTiming', data.timing || '--');
        setText('opMainNarrative', data.narrative?.[0] || '--');
        setText('opRecommendation', data.operational_recommendation || '--');
        setText('opChartTitle', `${data.symbol || state.symbol} · ${data.timeframe || state.timeframe}`);

        renderNarrative(data.narrative || []);
        renderCandleFlow(data.operacional_candle_flow || []);
        renderThreeCandlePattern(data.three_candle_pattern || data.institutional_map?.three_candle_pattern || {});
        renderStructure(data);
        renderList('opConfirmations', data.operacional_confirmations || [], 'check-circle');
        renderList('opInvalidations', data.operacional_invalidations || [], 'triangle-exclamation');
        renderCalibration(data.operacional_calibration || data.institutional_map?.calibration || {});
        renderRisk(opRisk);
        renderLiveFeed(data.operacional_live || []);
        renderOperationalSignal(opSignal);
        const markers = window.VisualAIOverlays?.buildOperationalMarkers(candlePayload?.candles || [], data) || [];
        state.chartEngine?.applyMarkers(markers);
        renderZoneLines(opChart.price_lines || [], data.operacional_zones || {}, candlePayload?.candles || []);
        state.chartEngine?.applyZones?.(opChart.zones || []);
        updateContextState(opContext);
    }

    function renderNarrative(items) {
        const container = $('opNarrative');
        container.innerHTML = items.length ? items.map((item) => (
            `<div class="live-message-row"><i class="fas fa-wave-square"></i><span>${escapeHtml(item)}</span></div>`
        )).join('') : '<div class="live-empty-signal">Sem narrativa operacional no momento.</div>';
    }

    function renderCandleFlow(flow) {
        const container = $('opCandleFlow');
        container.innerHTML = flow.length ? flow.map((item) => {
            const directionClass = item.direction === 'comprador' ? 'buy' : item.direction === 'vendedor' ? 'sell' : 'wait';
            const tags = (item.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join('');
            return `
                <div class="operacional-candle ${directionClass}">
                    <div>
                        <strong>${escapeHtml(item.direction)}</strong>
                        <small>${formatTime(item.time)}</small>
                    </div>
                    <p>${escapeHtml(item.reading)}</p>
                    <div class="operacional-candle-metrics">
                        <span>Corpo ${item.body_strength}%</span>
                        <span>Pavio sup. ${item.upper_wick_pct}%</span>
                        <span>Pavio inf. ${item.lower_wick_pct}%</span>
                        <span>Vol ${item.volume_ratio}x</span>
                    </div>
                    <div class="operacional-tags">${tags}</div>
                </div>
            `;
        }).join('') : '<div class="live-empty-signal">Aguardando candles suficientes.</div>';
    }

    function renderThreeCandlePattern(pattern) {
        const container = $('opThreeCandlePattern');
        if (!container) return;
        const candle1 = pattern.candle1 || {};
        const candle2 = pattern.candle2 || {};
        const candle3 = pattern.candle3 || {};
        const rows = [
            ['Status do padrão', pattern.status || '--'],
            ['Score do padrão', Number.isFinite(Number(pattern.score)) ? `${Math.round(Number(pattern.score))}/100` : '--'],
            ['Classificação', pattern.classification || '--'],
            ['Candle 1: alvo', candle1.reading || '--'],
            ['Candle 2: negação', candle2.reading || '--'],
            ['Candle 3: teste', candle3.reading || '--'],
            ['Região do padrão', pattern.region ? `${formatPrice(pattern.region.low)} / ${formatPrice(pattern.region.high)}` : '--'],
            ['Liquidez envolvida', pattern.liquidity?.reading || pattern.liquidity?.dominant || '--'],
            ['Entrada técnica', formatPrice(pattern.entry)],
            ['Stop técnico', formatPrice(pattern.stop)],
            ['Alvo provável', formatPrice(pattern.target)],
            ['Invalidação', pattern.invalidation || '--'],
            ['Leitura', pattern.explanation || '--'],
        ];
        container.innerHTML = rows.map(([label, value]) => (
            `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || '--')}</strong></div>`
        )).join('');
    }

    function renderStructure(data) {
        const map = data.institutional_map || {};
        const zones = data.operacional_zones || {};
        const context = data.operacional_context || {};
        const liquidity = data.operacional_liquidity || {};
        const triggers = map.triggers || {};
        const manipulation = map.manipulation || {};
        const fractal = map.fractal || {};
        const behavior = map.behavior || data.operacional_behavior || {};
        const obligation = map.price_obligation || {};
        const liquidityClass = liquidity.classification || {};
        const probabilities = map.probabilities || data.probabilities || {};
        const risk = data.operacional_risk || {};
        const fib = data.operacional_fibonacci || {};
        const threeCandle = data.three_candle_pattern || map.three_candle_pattern || {};
        const blockers = data.operation_blockers || map.operation_blockers || [];
        const rows = [
            ['Tendencia Macro', context.macro_trend || map.macro_trend?.trend],
            ['Tendencia Micro', context.micro_trend || map.micro_trend?.trend],
            ['Fractal 1m/5m/15m', fractal.reading || context.fractal_alignment],
            ['Timeframe dominante', `${context.dominant_timeframe || fractal.dominant_timeframe || '--'} ${context.dominant_timeframe_trend || fractal.dominant_trend || ''}`],
            ['Intencao do movimento', behavior.intention || context.behavioral_intention],
            ['Forca real', behavior.force_real || context.force_real],
            ['Continuidade', behavior.continuity_quality || context.continuity_quality],
            ['Absorcao / Exaustao', `${behavior.absorption ? 'absorcao' : 'sem absorcao'} / ${behavior.exhaustion ? 'exaustao' : 'sem exaustao'}`],
            ['Posicao no 50%', context.position_50 || fib.reading],
            ['Liquidez acima', `${formatPrice(liquidity.seller_stops_above || zones.upper_liquidity)} - stops de vendedores`],
            ['Liquidez abaixo', `${formatPrice(liquidity.buyer_stops_below || zones.lower_liquidity)} - stops de compradores`],
            ['Classificacao da liquidez', liquidityClass.reading || liquidityClass.dominant],
            ['Equal highs', formatEqualLevels(liquidity.equal_highs)],
            ['Equal lows', formatEqualLevels(liquidity.equal_lows)],
            ['Gatilho ativo', triggers.active || '--'],
            ['Stops provaveis', triggers.stop_activation_zone ? formatPrice(triggers.stop_activation_zone) : `${formatPrice(liquidity.seller_stops_above)} / ${formatPrice(liquidity.buyer_stops_below)}`],
            ['Possivel manipulacao', manipulation.detected ? manipulation.reading : 'Sem sweep objetivo no candle atual'],
            ['Obrigacao do preco', `${obligation.status || 'ativa'} - ${obligation.text || '--'}`],
            ['Padrão de 3 candles', `${threeCandle.status || '--'} - ${threeCandle.classification || '--'}`],
            ['Bloqueios operacionais', blockers.length ? blockers.join(' / ') : 'Sem bloqueio dominante'],
            ['Prob. continuacao', `${probabilities.continuation ?? '--'}%`],
            ['Prob. reversao', `${probabilities.reversal ?? '--'}%`],
            ['Melhor regiao de entrada', risk.best_entry_region || '--'],
            ['Regiao de invalidacao', formatPrice(risk.invalidation_region || risk.technical_stop)],
            ['Alvos provaveis', `${formatPrice(risk.take_profit_1)} / ${formatPrice(risk.take_profit_2)}`],
        ];
        $('opStructure').innerHTML = rows.map(([label, value]) => (
            `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || '--')}</strong></div>`
        )).join('');
    }

    function renderList(id, items, icon) {
        const container = $(id);
        container.innerHTML = items.length ? items.map((item) => (
            `<div class="live-message-row"><i class="fas fa-${icon}"></i><span>${escapeHtml(item)}</span></div>`
        )).join('') : '<div class="live-empty-signal">Nenhum item dominante.</div>';
    }

    function renderRisk(risk) {
        const rows = [
            ['Referencia', formatPrice(risk.reference_price)],
            ['Stop tecnico', formatPrice(risk.technical_stop)],
            ['Parcial', formatPrice(risk.partial_target)],
            ['RR', risk.risk_reward ? `${risk.risk_reward}:1` : '--'],
            ['Invalidação', risk.invalidation || '--'],
            ['Qualidade', risk.entry_quality || '--'],
        ];
        $('opRisk').innerHTML = rows.map(([label, value]) => (
            `<div class="level"><span class="level-name">${escapeHtml(label)}</span><span class="level-price">${escapeHtml(value)}</span></div>`
        )).join('');
    }

    function renderCalibration(calibration) {
        const summaryBox = $('opCalibrationSummary');
        const logBox = $('opCalibrationLog');
        if (!summaryBox || !logBox) return;
        const summary = calibration.summary || {};
        const records = Array.isArray(calibration.records) ? calibration.records.slice(-6).reverse() : [];
        summaryBox.innerHTML = [
            ['Modo', calibration.mode || 'calibracao_operacional'],
            ['Amostras', summary.samples ?? '--'],
            ['Alinhamento', `${summary.alignment_rate ?? 0}%`],
            ['Divergencias', summary.diverged ?? '--'],
        ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
        logBox.innerHTML = records.length ? records.map((item) => `
            <div class="operacional-calibration-item ${item.result === 'alinhou' ? 'positive' : item.result === 'divergiu' ? 'negative' : 'wait'}">
                <div><strong>${escapeHtml(item.result || '--')}</strong><span>${formatTime(item.time)}</span></div>
                <p>${escapeHtml(item.candle || '--')}</p>
                <small>Previsto ${escapeHtml(item.predicted || '--')} / Real ${escapeHtml(item.realized || '--')} / Score ${escapeHtml(item.score ?? '--')}</small>
            </div>
        `).join('') : '<div class="live-empty-signal">Calibracao aguardando candles.</div>';
    }

    function renderLiveFeed(items) {
        renderList('opLiveFeed', items || [], 'satellite-dish');
    }

    function renderOperationalSignal(signal) {
        const rows = [
            ['Ativo', signal.asset || signal.symbol || state.symbol],
            ['Timeframe', signal.timeframe || state.timeframe],
            ['Direcao contextual', signal.direction || 'NEUTRO'],
            ['Status', signal.status || 'analisando'],
            ['Entrada', formatPrice(signal.entry)],
            ['Stop', formatPrice(signal.stop)],
            ['Take 1', formatPrice(signal.take_profit_1)],
            ['Take 2', formatPrice(signal.take_profit_2)],
            ['R/R', signal.risk_reward ? `${signal.risk_reward}:1` : '--'],
            ['Liquidez alvo', signal.liquidity_target || '--'],
            ['Gatilho', signal.trigger || '--'],
            ['Comportamento', signal.behavior || '--'],
            ['Obrigacao', signal.price_obligation_status || '--'],
            ['Bloqueio', signal.blocked ? (signal.operation_blockers || []).join(' / ') : 'Sem bloqueio'],
            ['Padrão 3C', signal.three_candle_pattern ? `${signal.three_candle_pattern.status || '--'} / ${signal.three_candle_pattern.score ?? '--'}` : '--'],
            ['Motivo', signal.explanation || signal.operational_reason || '--'],
        ];
        $('opSignalBox').innerHTML = rows.map(([label, value]) => (
            `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || '--')}</strong></div>`
        )).join('');
    }

    async function refreshLive() {
        try {
            const response = await fetch(`/api/operacional/live/${state.symbol}/${state.timeframe}?limit=260`);
            const data = await response.json();
            if (data?.success) {
                renderLiveFeed(data.operacional_live || []);
                renderOperationalSignal(data.operacional_signal || {});
            }
        } catch (error) {
            // Mantem a ultima leitura visivel.
        }
    }

    function scheduleLive() {
        clearInterval(state.liveTimer);
        state.liveTimer = setInterval(refreshLive, 12000);
    }

    function renderZoneLines(markLines, zones, candles) {
        if (!state.chartEngine || !candles.length) return;
        const lines = Array.isArray(markLines) && markLines.length ? markLines : [
            ['Liq. abaixo', zones.lower_liquidity, '#EF4444'],
            ['Liq. acima', zones.upper_liquidity, '#22C55E'],
            ['50% micro', zones.micro_50, '#38BDF8'],
            ['50% macro', zones.macro_50, '#A78BFA'],
            ['Liquidez sup.', zones.upper_liquidity, '#D4AF37'],
            ['Liquidez inf.', zones.lower_liquidity, '#38BDF8'],
        ].map(([label, price, color]) => ({ label, price, color }));
        state.chartEngine.applyLevels(lines.map((line) => ({
            label: line.label,
            price: line.price,
            color: line.color,
            lineWidth: line.type === 'entry' ? 2 : 1,
        })));
    }

    function updateContextState(context) {
        const card = $('opContextCard');
        if (!card) return;
        card.dataset.state = context?.risk === 'alto' ? 'HIGH_RISK' : context?.label === 'Contexto favoravel' ? 'CONSERVATIVE_ENTRY' : 'WAITING_CONFIRMATION';
    }

    function renderError(error) {
        setText('opDominantContext', 'SEM LEITURA');
        setText('opMainNarrative', error.message || 'Falha ao carregar leitura operacional.');
        $('opNarrative').innerHTML = `<div class="live-empty-signal">${escapeHtml(error.message || 'Erro operacional.')}</div>`;
    }

    function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value == null || value === '' ? '--' : value;
    }

    function statusLabel(status) {
        const labels = { open: 'Aberto', closed: 'Fechado', fallback: 'Fallback', no_data: 'Sem dados', unknown: 'Indefinido' };
        return labels[status] || status || '--';
    }

    function formatPrice(value) {
        const num = Number(value);
        if (!Number.isFinite(num)) return '--';
        return num >= 100 ? num.toFixed(2) : num.toFixed(5);
    }

    function formatEqualLevels(levels) {
        if (!Array.isArray(levels) || !levels.length) return '--';
        return levels.map((item) => `${formatPrice(item.price)} (${item.touches} toques)`).join(' / ');
    }

    function formatTime(timestamp) {
        if (!timestamp) return '--';
        return new Date(timestamp * 1000).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
})();
