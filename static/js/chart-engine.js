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
            this.indicatorSeries = {};
            this.indicatorSignature = '';
            this.markerSignature = '';
            this.resizeFrame = null;
            this.pendingCandle = null;
            this.pendingVolume = null;
            this.updateFrame = null;
            this.lastCandles = [];
            this.lastVolumes = [];
        }

        init() {
            if (!this.container || !window.LightweightCharts) return null;
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
            this.candleSeries = this.chart.addCandlestickSeries({
                upColor: '#20D18C',
                downColor: '#F05252',
                borderUpColor: '#20D18C',
                borderDownColor: '#F05252',
                wickUpColor: '#20D18C',
                wickDownColor: '#F05252',
            });
            this.volumeSeries = this.chart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: '',
                scaleMargins: { top: 0.82, bottom: 0 },
            });
            this.setupIndicators(this.options.indicators || {});
            return this;
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
            this.lastCandles = Array.isArray(candles) ? candles.slice(-320) : [];
            this.lastVolumes = Array.isArray(volumes) ? volumes.slice(-320) : [];
            this.candleSeries?.setData(this.lastCandles);
            this.volumeSeries?.setData(this.lastVolumes);
            if (fit) this.fit();
        }

        setupIndicators(indicators) {
            if (!this.chart) return;
            Object.entries(indicators || {}).forEach(([key, options]) => {
                this.indicatorSeries[key] = this.chart.addLineSeries(options);
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
            if (!candle?.time) return;
            this.pendingCandle = candle;
            this.pendingVolume = volume;
            if (this.updateFrame) return;
            this.updateFrame = requestAnimationFrame(() => {
                this.updateFrame = null;
                const nextCandle = this.pendingCandle;
                const nextVolume = this.pendingVolume;
                this.pendingCandle = null;
                this.pendingVolume = null;
                this.candleSeries?.update(nextCandle);
                if (nextVolume) this.volumeSeries?.update(nextVolume);
                this.upsertCandle(nextCandle);
                if (nextVolume) this.upsertVolume(nextVolume);
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
            if (!this.candleSeries?.setMarkers) return;
            const normalized = (Array.isArray(markers) ? markers : [])
                .filter((item) => item?.time && item?.text)
                .slice(-30);
            const signature = normalized.map((item) => `${item.time}:${item.position}:${item.text}`).join('|');
            if (signature === this.markerSignature) return;
            this.markerSignature = signature;
            this.candleSeries.setMarkers(normalized);
        }

        applyLevels(levels) {
            const next = new Map();
            (Array.isArray(levels) ? levels : []).forEach((level) => {
                const price = Number(level.price);
                if (!Number.isFinite(price)) return;
                const key = `${level.label}:${price}:${level.color}`;
                next.set(key, {
                    price,
                    color: level.color || '#38bdf8',
                    lineWidth: level.lineWidth || 2,
                    lineStyle: level.lineStyle ?? LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: level.axisLabelVisible !== false,
                    title: level.label || '',
                });
            });
            this.syncLines(this.priceLines, next);
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

        syncLines(current, next) {
            current.forEach((line, key) => {
                if (!next.has(key)) {
                    this.candleSeries?.removePriceLine(line);
                    current.delete(key);
                }
            });
            next.forEach((config, key) => {
                if (current.has(key)) return;
                current.set(key, this.candleSeries.createPriceLine(config));
            });
        }

        clearOverlays() {
            this.clearLineMap(this.priceLines);
            this.clearLineMap(this.overlayLines);
            this.markerSignature = '';
            this.candleSeries?.setMarkers?.([]);
        }

        clearLineMap(map) {
            map.forEach((line) => this.candleSeries?.removePriceLine(line));
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
