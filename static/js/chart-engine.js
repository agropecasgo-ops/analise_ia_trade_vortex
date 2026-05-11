(function () {
    class LiveChartEngine {
        constructor(containerId, options = {}) {
            this.container = document.getElementById(containerId);
            this.options = options;
            this.chart = null;
            this.candleSeries = null;
            this.volumeSeries = null;
            this.priceLines = new Map();
            this.overlayLines = new Map();
            this.structureLines = new Map();
            this.structureZones = new Map();
            this.indicatorSeries = {};
            this.indicatorSignature = '';
            this.markerSignature = '';
            this.resizeFrame = null;
            this.pendingCandle = null;
            this.pendingVolume = null;
            this.updateFrame = null;
            this.lastCandles = [];
            this.lastVolumes = [];
            this.visualMarkers = [];
            this.markerLayer = null;
            this.structureOverlays = {
                bos: [],
                choch: [],
                fvg: [],
            };
        }

        drawBuySignal(time, price) {
            this.addVisualMarker({
                time,
                position: 'belowBar',
                color: '#4CAF50',
                shape: 'arrowUp',
                text: 'Buy',
                price,
            });
        }

        drawSellSignal(time, price) {
            this.addVisualMarker({
                time,
                position: 'aboveBar',
                color: '#F44336',
                shape: 'arrowDown',
                text: 'Sell',
                price,
            });
        }

        drawEntry(time, price) {
            this.addVisualMarker({
                time,
                position: Number.isFinite(Number(price)) ? 'atPriceMiddle' : 'belowBar',
                color: '#2196F3',
                shape: 'circle',
                text: 'Entry',
                price,
            });
            this.applyLevel('Entrada', price, '#2196F3');
        }

        drawStop(time, price) {
            this.addVisualMarker({
                time,
                position: Number.isFinite(Number(price)) ? 'atPriceMiddle' : 'aboveBar',
                color: '#FF5722',
                shape: 'circle',
                text: 'Stop',
                price,
            });
            this.applyLevel('Stop', price, '#FF5722');
        }

        drawTakeProfit(time, price) {
            this.addVisualMarker({
                time,
                position: Number.isFinite(Number(price)) ? 'atPriceMiddle' : 'belowBar',
                color: '#8BC34A',
                shape: 'circle',
                text: 'Take Profit',
                price,
            });
            this.applyLevel('Take Profit', price, '#8BC34A');
        }

        prepareOverlayStructure() {
            this.structureOverlays = {
                bos: [],
                choch: [],
                fvg: [],
            };
            return this.structureOverlays;
        }

        init() {
            if (!this.container || !window.LightweightCharts) return null;
            if (!this.chart) {
                this.container.innerHTML = '';
                this.chart = LightweightCharts.createChart(this.container, {
                    width: this.container.clientWidth,
                    height: this.height(),
                    layout: {
                        background: { type: 'solid', color: '#030712' },
                        textColor: '#DCEBFF',
                        fontFamily: 'Inter, Arial, sans-serif',
                    },
                    grid: {
                        horzLines: { color: 'rgba(80, 180, 255, 0.075)' },
                        vertLines: { color: 'rgba(255, 255, 255, 0.032)' },
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
                    watermark: this.options.watermark || undefined,
                });
                this.candleSeries = this.addSeries('Candlestick', {
                    upColor: '#20D18C',
                    downColor: '#F05252',
                    borderUpColor: '#20D18C',
                    borderDownColor: '#F05252',
                    wickUpColor: '#20D18C',
                    wickDownColor: '#F05252',
                });
                this.volumeSeries = this.addSeries('Histogram', {
                    priceFormat: { type: 'volume' },
                    priceScaleId: '',
                    scaleMargins: { top: 0.82, bottom: 0 },
                });
                this.setupIndicators(this.options.indicators || {});
                this.prepareOverlayStructure();
            }
            return this;
        }

        addSeries(type, options) {
            const constructors = {
                Candlestick: LightweightCharts.CandlestickSeries,
                Histogram: LightweightCharts.HistogramSeries,
                Line: LightweightCharts.LineSeries,
            };
            const legacy = {
                Candlestick: 'addCandlestickSeries',
                Histogram: 'addHistogramSeries',
                Line: 'addLineSeries',
            };
            if (typeof this.chart?.addSeries === 'function' && constructors[type]) {
                return this.chart.addSeries(constructors[type], options);
            }
            return this.chart?.[legacy[type]]?.(options);
        }

        height() {
            return Math.max(this.container?.clientHeight || 0, this.options.minHeight || 620);
        }

        resize() {
            if (!this.container || !this.chart) return;
            cancelAnimationFrame(this.resizeFrame);
            this.resizeFrame = requestAnimationFrame(() => {
                this.chart.applyOptions({
                    width: this.container.clientWidth,
                    height: this.height(),
                });
            });
        }

        setData(candles, volumes, fit = false) {
            const normalizedCandles = this.normalizeCandles(candles);
            const normalizedVolumes = Array.isArray(volumes) && volumes.length
                ? this.normalizeVolumes(volumes)
                : this.volumesFromCandles(normalizedCandles);

            this.lastCandles = normalizedCandles.slice(-320);
            this.lastVolumes = normalizedVolumes.slice(-320);
            this.candleSeries?.setData(this.lastCandles);
            this.volumeSeries?.setData(this.lastVolumes);
            if (fit) this.fit();
        }

        normalizeCandles(candles) {
            return (Array.isArray(candles) ? candles : [])
                .map((item) => {
                    const time = this.normalizeTime(item?.time ?? item?.timestamp ?? item?.date ?? item?.datetime);
                    const open = Number(item?.open ?? item?.o);
                    const high = Number(item?.high ?? item?.h);
                    const low = Number(item?.low ?? item?.l);
                    const close = Number(item?.close ?? item?.c);

                    // Ensure all required fields are finite numbers and time is valid
                    if (!time || ![open, high, low, close].every(Number.isFinite)) {
                        console.warn("Invalid candle data received:", item); // Log invalid data
                        return null;
                    }
                    return { time, open, high, low, close, volume: Number(item?.volume ?? item?.v ?? 0) || 0 };
                })
                .filter(Boolean)
                .sort((a, b) => a.time - b.time);
        }

        normalizeVolumes(volumes) {
            return (Array.isArray(volumes) ? volumes : [])
                .map((item) => {
                    const time = this.normalizeTime(item?.time ?? item?.timestamp ?? item?.date ?? item?.datetime);
                    const value = Number(item?.value ?? item?.volume ?? item?.v);
                    if (!time || !Number.isFinite(value)) return null;
                    return { time, value, color: item?.color || 'rgba(56, 189, 248, 0.35)' };
                })
                .filter(Boolean)
                .sort((a, b) => a.time - b.time);
        }

        volumesFromCandles(candles) {
            return candles.map((item) => ({
                time: item.time,
                value: Number(item.volume) || 0,
                color: item.close >= item.open ? 'rgba(32, 209, 140, 0.35)' : 'rgba(240, 82, 82, 0.35)',
            }));
        }

        normalizeTime(value) {
            if (typeof value === 'number') return value > 9999999999 ? Math.floor(value / 1000) : value;
            if (typeof value === 'string') {
                if (/^\d+$/.test(value)) return this.normalizeTime(Number(value));
                const parsed = Date.parse(value);
                if (Number.isFinite(parsed)) return Math.floor(parsed / 1000);
            }
            return null;
        }

        setupIndicators(indicators) {
            if (!this.chart) return;
            Object.entries(indicators || {}).forEach(([key, options]) => {
                this.indicatorSeries[key] = this.addSeries('Line', options);
            });
        }

        setIndicators(overlays) {
            const entries = Object.entries(overlays || {});
            const signature = entries.map(([key, values]) => `${key}:${Array.isArray(values) ? values.length : 0}:${Array.isArray(values) && values.length ? values[values.length - 1]?.time : ''}`).join('|');
            if (signature === this.indicatorSignature) return;
            this.indicatorSignature = signature;
            entries.forEach(([key, values]) => {
                this.indicatorSeries[key]?.setData(Array.isArray(values) ? values.filter(Boolean) : []);
            });
        }

        update(candle, volume) {
            const nextCandle = this.normalizeCandles([candle])[0];
            const nextVolume = this.normalizeVolumes(volume ? [volume] : [nextCandle])[0];
            if (!nextCandle?.time) return;

            this.pendingCandle = nextCandle;
            this.pendingVolume = nextVolume;
            if (this.updateFrame) return;
            this.updateFrame = requestAnimationFrame(() => {
                const pendingCandle = this.pendingCandle;
                const pendingVolume = this.pendingVolume;
                this.pendingCandle = null;
                this.pendingVolume = null;
                this.updateFrame = null;
                if (!pendingCandle) return;

                this.candleSeries?.update(pendingCandle);
                this.upsertCandle(pendingCandle);

                if (pendingVolume && Number.isFinite(pendingVolume.value)) {
                    this.volumeSeries?.update(pendingVolume);
                    this.upsertVolume(pendingVolume);
                }
            });
        }

        upsertCandle(candle) {
            const index = this.lastCandles.findIndex((item) => item.time === candle.time);
            if (index >= 0) {
                this.lastCandles[index] = candle;
            } else {
                this.lastCandles.push(candle);
            }
            if (this.lastCandles.length > 320) this.lastCandles = this.lastCandles.slice(-320);
        }

        upsertVolume(volume) {
            const index = this.lastVolumes.findIndex((item) => item.time === volume.time);
            if (index >= 0) {
                this.lastVolumes[index] = volume;
            } else {
                this.lastVolumes.push(volume);
            }
            if (this.lastVolumes.length > 320) this.lastVolumes = this.lastVolumes.slice(-320);
        }

        applyMarkers(markers) {
            const normalized = this.normalizeMarkers(markers).slice(-60);
            const signature = normalized.map((item) => this.markerKey(item)).join('|');
            if (signature === this.markerSignature) return;
            this.markerSignature = signature;
            this.visualMarkers = normalized;
            this.renderMarkers();
        }

        addVisualMarker(marker) {
            const normalized = this.normalizeMarkers([marker])[0];
            if (!normalized) return;
            const key = this.markerKey(normalized);
            this.visualMarkers = this.visualMarkers.filter((item) => this.markerKey(item) !== key);
            this.visualMarkers.push(normalized);
            this.visualMarkers = this.visualMarkers.slice(-60);
            this.markerSignature = '';
            this.renderMarkers();
        }

        normalizeMarkers(markers) {
            return (Array.isArray(markers) ? markers : [])
                .map((item) => {
                    const time = this.normalizeTime(item?.time ?? item?.timestamp ?? item?.date ?? item?.datetime);
                    const price = Number(item?.price);
                    if (!time || !item?.text) return null;
                    const marker = {
                        time,
                        position: item.position || 'aboveBar',
                        color: item.color || '#38bdf8',
                        shape: item.shape || 'circle',
                        text: String(item.text),
                    };
                    if (Number.isFinite(price)) marker.price = price;
                    return marker;
                })
                .filter(Boolean)
                .sort((a, b) => a.time - b.time);
        }

        markerKey(marker) {
            return `${marker.time}:${marker.position}:${marker.text}:${marker.price ?? ''}`;
        }

        renderMarkers() {
            if (!this.candleSeries) return;
            if (typeof this.candleSeries.setMarkers === 'function') {
                this.candleSeries.setMarkers(this.visualMarkers);
                return;
            }
            if (this.markerLayer?.setMarkers) {
                this.markerLayer.setMarkers(this.visualMarkers);
                return;
            }
            if (typeof LightweightCharts.createSeriesMarkers === 'function') {
                this.markerLayer = LightweightCharts.createSeriesMarkers(this.candleSeries, this.visualMarkers);
            }
        }

        applyLevel(label, price, color) {
            const value = Number(price);
            if (!Number.isFinite(value) || !this.candleSeries?.createPriceLine) return;
            const key = `${label}:${value}:${color}`;
            if (this.priceLines.has(key)) return;
            this.priceLines.set(key, this.candleSeries.createPriceLine(this.lineConfig({
                label,
                price: value,
                color,
            })));
        }

        applyLevels(levels) {
            const next = new Map();
            (Array.isArray(levels) ? levels : []).forEach((level) => {
                const price = Number(level.price);
                if (!Number.isFinite(price)) return;
                const label = level.label || level.title || '';
                const key = `${label}:${price}:${level.color}`;
                next.set(key, this.lineConfig({ ...level, label, price }));
            });
            this.syncLines(this.priceLines, next);
        }

        lineConfig(level) {
            return {
                price: Number(level.price),
                color: level.color || '#38bdf8',
                lineWidth: level.lineWidth || 2,
                lineStyle: level.lineStyle ?? LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: level.axisLabelVisible !== false,
                title: level.label || level.title || '',
            };
        }

        applyZones(zones) {
            const next = new Map();
            (Array.isArray(zones) ? zones : []).forEach((zone) => {
                const low = Number(zone.low);
                const high = Number(zone.high);
                if (!Number.isFinite(low) || !Number.isFinite(high)) return;
                const color = this.withAlpha(zone.color || '#38bdf8', zone.opacity || 0.24);
                [
                    { price: high, suffix: 'H' },
                    { price: low, suffix: 'L' },
                ].forEach((line) => {
                    const key = `${zone.label}:${zone.type}:${line.suffix}:${line.price}:${color}:${zone.active ? 1 : 0}`;
                    next.set(key, {
                        price: line.price,
                        color,
                        lineWidth: zone.active ? 2 : 1,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: false,
                        title: `${zone.label} ${line.suffix}`,
                    });
                });
            });
            this.syncLines(this.overlayLines, next);
        }

        applyStructureOverlays(structure = {}) {
            this.structureOverlays = {
                bos: Array.isArray(structure.bos) ? structure.bos : [],
                choch: Array.isArray(structure.choch) ? structure.choch : [],
                fvg: Array.isArray(structure.fvg) ? structure.fvg : [],
            };

            const structureLevels = new Map();
            [
                ...this.structureOverlays.bos.map((item) => this.structureLevel(item, 'BOS', '#22C55E')),
                ...this.structureOverlays.choch.map((item) => this.structureLevel(item, 'CHOCH', '#F59E0B')),
            ].filter(Boolean).forEach((level) => {
                const key = `${level.label}:${level.price}:${level.color}`;
                structureLevels.set(key, this.lineConfig(level));
            });

            const fvgZones = new Map();
            this.structureOverlays.fvg
                .map((item) => this.structureZone(item, 'FVG', '#F59E0B'))
                .filter(Boolean)
                .forEach((zone) => {
                    const color = this.withAlpha(zone.color || '#F59E0B', zone.opacity || 0.2);
                    [
                        { price: zone.high, suffix: 'H' },
                        { price: zone.low, suffix: 'L' },
                    ].forEach((line) => {
                        const key = `${zone.label}:${zone.type}:${line.suffix}:${line.price}:${color}`;
                        fvgZones.set(key, this.lineConfig({
                            label: `${zone.label} ${line.suffix}`,
                            price: line.price,
                            color,
                            lineWidth: zone.active ? 2 : 1,
                            lineStyle: LightweightCharts.LineStyle.Dotted,
                            axisLabelVisible: false,
                        }));
                    });
                });

            this.syncLines(this.structureLines, structureLevels);
            this.syncLines(this.structureZones, fvgZones);
        }

        structureLevel(item, label, color) {
            const price = Number(item?.price ?? item?.level);
            if (!Number.isFinite(price)) return null;
            return {
                label: item?.label || label,
                price,
                color: item?.color || color,
                lineWidth: item?.lineWidth || 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
            };
        }

        structureZone(item, label, color) {
            const low = Number(item?.low ?? item?.bottom ?? item?.min);
            const high = Number(item?.high ?? item?.top ?? item?.max);
            if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
            return {
                label: item?.label || label,
                type: item?.type || label.toLowerCase(),
                low: Math.min(low, high),
                high: Math.max(low, high),
                color: item?.color || color,
                opacity: item?.opacity || 0.2,
                active: item?.active !== false,
            };
        }

        syncLines(current, next) {
            current.forEach((line, key) => {
                if (!next.has(key)) {
                    if (line) this.candleSeries?.removePriceLine(line);
                    current.delete(key);
                }
            });
            next.forEach((config, key) => {
                if (current.has(key) || !this.candleSeries?.createPriceLine) return;
                current.set(key, this.candleSeries.createPriceLine(config));
            });
        }

        clearOverlays() {
            this.clearLineMap(this.priceLines);
            this.clearLineMap(this.overlayLines);
            this.clearLineMap(this.structureLines);
            this.clearLineMap(this.structureZones);
            this.markerSignature = '';
            this.visualMarkers = [];
            this.renderMarkers();
            this.prepareOverlayStructure();
        }

        clearLineMap(map) {
            map.forEach((line) => {
                if (line) this.candleSeries?.removePriceLine(line);
            });
            map.clear();
        }

        fit() {
            this.chart?.timeScale().fitContent();
        }

        withAlpha(color, alpha) {
            const hex = String(color || '').replace('#', '');
            if (hex.length !== 6) return color;
            const value = Math.round(Math.max(0.08, Math.min(alpha, 0.9)) * 255).toString(16).padStart(2, '0');
            return `#${hex}${value}`;
        }
    }

    window.LiveChartEngine = LiveChartEngine;
    window.InstitutionalChartEngine = LiveChartEngine;
})();
