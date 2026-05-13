(function () {
    class InstitutionalReplay {
        constructor() {
            this.payload = null;
            this.frameIndex = 0;
            this.timer = null;
            this.playing = false;
            this.speedMs = 850;
            this.bind();
        }

        bind() {
            document.getElementById('replayLoadBtn')?.addEventListener('click', () => this.load());
            document.getElementById('replayPlayPause')?.addEventListener('click', async () => {
                if (!this.payload) await this.load();
                this.toggle();
            });
            document.getElementById('replayStepBtn')?.addEventListener('click', async () => {
                if (!this.payload) await this.load();
                this.pause();
                this.step();
            });
        }

        async load() {
            const asset = document.getElementById('institutionalAsset')?.value || 'BTCUSDT';
            const assetType = document.getElementById('institutionalAssetType')?.value || 'crypto';
            const timeframe = document.getElementById('institutionalTimeframe')?.value || '15m';
            this.pause();
            this.setSummary('Carregando replay IA...');
            try {
                const url = `/api/institutional/replay?symbol=${encodeURIComponent(asset)}&timeframe=${encodeURIComponent(timeframe)}&assetType=${encodeURIComponent(assetType)}&limit=180`;
                const response = await fetch(url);
                const payload = await response.json();
                this.payload = payload;
                this.frameIndex = 0;
                this.setSummary(payload.summary || 'Replay carregado.');
                this.render();
            } catch (error) {
                this.setSummary('Replay indisponivel.');
                this.setText('replayCurrentExplanation', error?.message || 'Falha ao carregar replay.');
            }
        }

        toggle() {
            if (this.playing) {
                this.pause();
                return;
            }
            this.play();
        }

        play() {
            if (!this.payload?.frames?.length) return;
            this.playing = true;
            this.setPlayIcon(true);
            clearInterval(this.timer);
            this.timer = setInterval(() => {
                if (!this.step()) this.pause();
            }, this.speedMs);
        }

        pause() {
            this.playing = false;
            this.setPlayIcon(false);
            clearInterval(this.timer);
            this.timer = null;
        }

        step() {
            if (!this.payload?.frames?.length) return false;
            if (this.frameIndex < this.payload.frames.length - 1) {
                this.frameIndex += 1;
                this.render();
                return true;
            }
            this.render();
            return false;
        }

        render() {
            const frames = this.payload?.frames || [];
            const frame = frames[this.frameIndex];
            if (!frame) {
                this.renderEmpty();
                return;
            }
            const candleCount = Number(frame.index || 0) + 1;
            const candles = (this.payload.candles || []).slice(0, candleCount);
            const volumes = (this.payload.volumes || []).slice(0, candleCount);
            const chart = window.institutionalDesk?.chartEngine;
            chart?.setData(candles, volumes, false);
            chart?.clearOverlays?.();
            chart?.applyMarkers?.(this.markersUntil(frame.index));
            this.setText('replayCandleIndex', `${this.frameIndex + 1}/${frames.length}`);
            this.setText('replayTrend', frame.trend || frame.direction || '--');
            this.setText('replayScore', `${Math.round(Number(frame.score || 0))}/100`);
            this.setText('replayPhase', frame.marketPhase || '--');
            this.setText('replayCurrentExplanation', frame.explanation || '--');
            this.setProgress(((this.frameIndex + 1) / Math.max(frames.length, 1)) * 100);
            this.renderEvents(frame.index);
        }

        renderEmpty() {
            this.setText('replayCandleIndex', '--');
            this.setText('replayTrend', '--');
            this.setText('replayScore', '--');
            this.setText('replayPhase', '--');
            this.setText('replayCurrentExplanation', this.payload?.summary || 'Sem frames para reproduzir.');
            this.setProgress(0);
            this.renderEvents(-1);
        }

        markersUntil(index) {
            return (this.payload?.events || [])
                .filter((event) => Number(event.index) <= Number(index))
                .slice(-60)
                .map((event) => ({
                    time: event.time,
                    price: event.price,
                    position: this.markerPosition(event.kind),
                    shape: this.markerShape(event.kind),
                    color: this.markerColor(event.kind, event.importance),
                    text: this.markerText(event.kind),
                }));
        }

        renderEvents(index) {
            const container = document.getElementById('replayEvents');
            if (!container) return;
            const events = (this.payload?.events || [])
                .filter((event) => Number(event.index) <= Number(index))
                .slice(-30)
                .reverse();
            if (!events.length) {
                container.innerHTML = '<div class="replay-empty">Nenhum evento ate este candle.</div>';
                return;
            }
            container.innerHTML = events.map((event) => `
                <div class="replay-event ${this.escape(event.importance || '')}">
                    <span>${this.escape(event.kind || '--')} - Score ${this.escape(event.score ?? '--')}</span>
                    <strong>${this.escape(event.title || '--')}</strong>
                    <small>${this.escape(event.explanation || '')}</small>
                </div>
            `).join('');
        }

        markerText(kind) {
            return {
                TREND: 'Trend',
                BOS: 'BOS',
                CHOCH: 'CHOCH',
                SWEEP: 'Sweep',
                ORDER_BLOCK: 'OB',
                FVG: 'FVG',
                VOLUME: 'Vol',
                MANIPULATION: 'Trap',
                SCORE_80: '80+',
            }[kind] || String(kind || 'IA');
        }

        markerColor(kind, importance) {
            if (kind === 'SCORE_80') return '#D4AF37';
            if (kind === 'MANIPULATION') return '#EF4444';
            if (kind === 'SWEEP') return '#F59E0B';
            if (importance === 'high') return '#A78BFA';
            return '#38BDF8';
        }

        markerShape(kind) {
            if (kind === 'BOS' || kind === 'SCORE_80') return 'arrowUp';
            if (kind === 'CHOCH' || kind === 'MANIPULATION') return 'arrowDown';
            return 'circle';
        }

        markerPosition(kind) {
            if (kind === 'BOS' || kind === 'SCORE_80') return 'belowBar';
            return 'aboveBar';
        }

        setSummary(value) {
            this.setText('replaySummary', value);
        }

        setProgress(value) {
            const bar = document.getElementById('replayProgressBar');
            if (bar) bar.style.width = `${Math.max(0, Math.min(100, Number(value) || 0))}%`;
        }

        setPlayIcon(isPlaying) {
            const icon = document.querySelector('#replayPlayPause i');
            if (!icon) return;
            icon.className = isPlaying ? 'fas fa-pause' : 'fas fa-play';
        }

        setText(id, value) {
            const element = document.getElementById(id);
            if (element) element.textContent = value ?? '--';
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
        window.institutionalReplay = new InstitutionalReplay();
    });
})();
