(function () {
    function lastCandle(candles) {
        return Array.isArray(candles) && candles.length ? candles[candles.length - 1] : null;
    }

    function marker(time, position, shape, color, text) {
        if (!time || !text) return null;
        return { time, position, shape, color, text };
    }

    function compact(text, limit = 24) {
        text = String(text || '').trim();
        return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
    }

    function directionColor(direction) {
        const value = String(direction || '').toUpperCase();
        if (['BUY', 'COMPRA', 'BULLISH', 'BUY_FLOW'].includes(value)) return '#22C55E';
        if (['SELL', 'VENDA', 'BEARISH', 'SELL_FLOW'].includes(value)) return '#EF4444';
        if (value.includes('AGUARDAR') || value.includes('WAIT')) return '#FACC15';
        return '#38BDF8';
    }

    function buildCompleteMarkers(candles, analysis) {
        const last = lastCandle(candles);
        if (!last || !analysis) return [];
        const time = last.time;
        const markers = [];
        const cards = analysis.signal_cards || {};
        const technical = analysis.technical_reader || {};
        const details = technical.details || {};
        const smc = analysis.smc || {};
        const tape = analysis.tape_reading || {};
        const volume = analysis.volume_analysis || {};

        if (cards.label) {
            const up = cards.active === 'buy';
            const down = cards.active === 'sell';
            markers.push(marker(
                time,
                up ? 'belowBar' : 'aboveBar',
                up ? 'arrowUp' : down ? 'arrowDown' : 'circle',
                directionColor(cards.label),
                compact(cards.label.replace(' CONFIRMACAO', ''))
            ));
        }
        if (details.pullback?.detected) {
            markers.push(marker(time, 'belowBar', 'circle', '#38BDF8', 'Pullback'));
        }
        if (details.breakout?.detected) {
            markers.push(marker(time, 'aboveBar', 'arrowUp', '#FACC15', 'Rompimento'));
        }
        if (details.lateralization?.detected) {
            markers.push(marker(time, 'aboveBar', 'circle', '#94A3B8', 'Lateral'));
        }
        if (smc.false_breakout?.detected) {
            markers.push(marker(time, 'aboveBar', 'circle', '#F97316', 'Armadilha'));
        }
        if (smc.liquidity_sweep?.detected) {
            markers.push(marker(time, 'aboveBar', 'circle', '#A78BFA', 'Liquidez'));
        }
        if (tape.order_flow_bias === 'BUY_FLOW') {
            markers.push(marker(time, 'belowBar', 'circle', '#22C55E', 'Pressao compra'));
        }
        if (tape.order_flow_bias === 'SELL_FLOW') {
            markers.push(marker(time, 'aboveBar', 'circle', '#EF4444', 'Pressao venda'));
        }
        if (volume.exhaustion?.detected) {
            markers.push(marker(time, 'aboveBar', 'circle', '#F59E0B', 'Exaustao'));
        }
        return markers.filter(Boolean).slice(-8);
    }

    function buildOperationalMarkers(candles, readingOrStatus) {
        const last = lastCandle(candles);
        if (!last || !readingOrStatus) return [];
        const reading = readingOrStatus.reading || readingOrStatus.operacional_reading || readingOrStatus;
        const signal = readingOrStatus.signal || reading.operacional_signal || {};
        const candle = reading.operacional_current_candle || reading.current_candle || {};
        const breakout = reading.operacional_breakout || reading.breakout || {};
        const pullback = reading.operacional_pullback || reading.pullback || {};
        const liquidity = reading.operacional_liquidity || reading.liquidity || {};
        const time = candle.time || last.time;
        const markers = [];

        if (signal.direction && signal.direction !== 'NEUTRO') {
            markers.push(marker(
                time,
                signal.direction === 'COMPRA' ? 'belowBar' : 'aboveBar',
                signal.direction === 'COMPRA' ? 'arrowUp' : 'arrowDown',
                directionColor(signal.direction),
                signal.direction
            ));
        }
        if (pullback.valid_pullback) markers.push(marker(time, 'belowBar', 'circle', '#38BDF8', 'Pullback saudavel'));
        if (pullback.pullback_failure) markers.push(marker(time, 'aboveBar', 'circle', '#EF4444', 'Falha pullback'));
        if (breakout.valid_breakout) markers.push(marker(time, 'aboveBar', 'arrowUp', '#FACC15', 'Rompimento'));
        if (breakout.false_breakout) markers.push(marker(time, 'aboveBar', 'circle', '#F97316', 'Sem continuidade'));
        if (liquidity.sweep) markers.push(marker(time, 'aboveBar', 'circle', '#A78BFA', 'Liquidez'));
        if (Number(candle.upper_wick_pct || 0) >= 42) markers.push(marker(time, 'aboveBar', 'circle', '#F59E0B', 'Rejeicao topo'));
        if (Number(candle.lower_wick_pct || 0) >= 42) markers.push(marker(time, 'belowBar', 'circle', '#22C55E', 'Rejeicao fundo'));
        if (Number(candle.body_strength || 0) >= 65) markers.push(marker(time, 'belowBar', 'circle', '#D4AF37', 'Candle decisao'));
        return markers.filter(Boolean).slice(-8);
    }

    function set(series, baseMarkers, overlayMarkers) {
        if (!series?.setMarkers) return;
        const merged = [...(Array.isArray(baseMarkers) ? baseMarkers : []), ...(Array.isArray(overlayMarkers) ? overlayMarkers : [])];
        const deduped = [];
        const seen = new Set();
        merged.slice(-30).forEach((item) => {
            const key = `${item.time}:${item.position}:${item.text}`;
            if (seen.has(key)) return;
            seen.add(key);
            deduped.push(item);
        });
        series.setMarkers(deduped);
    }

    window.VisualAIOverlays = {
        buildCompleteMarkers,
        buildOperationalMarkers,
        set,
    };
})();
