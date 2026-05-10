class FinanceVoiceAssistant {
    constructor() {
        this.enabled = false;
        this.volume = 0.85;
        this.rate = 1;
        this.lang = 'pt-BR';
        this.voiceName = '';
        this.voices = [];
        this.lastSpoken = new Map();
        this.lastMessage = '';
        this.cooldownMs = 22000;
        this.loadSettings();
        this.loadVoices();
        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = () => this.loadVoices();
        }
    }

    loadSettings() {
        try {
            const saved = JSON.parse(localStorage.getItem('financeVoiceAssistant') || '{}');
            this.enabled = Boolean(saved.enabled);
            this.volume = Number(saved.volume ?? this.volume);
            this.rate = Number(saved.rate ?? this.rate);
            this.voiceName = saved.voiceName || '';
        } catch (error) {
            console.warn('Voice settings unavailable', error);
        }
    }

    saveSettings() {
        localStorage.setItem('financeVoiceAssistant', JSON.stringify({
            enabled: this.enabled,
            volume: this.volume,
            rate: this.rate,
            voiceName: this.voiceName,
        }));
    }

    loadVoices() {
        if (!('speechSynthesis' in window)) return [];
        this.voices = window.speechSynthesis.getVoices()
            .filter((voice) => String(voice.lang || '').toLowerCase().startsWith('pt') || String(voice.lang || '').toLowerCase().startsWith('en'));
        this.renderVoiceSelect();
        this.updateStatus();
        return this.voices;
    }

    bindControls(prefix = 'voice') {
        document.getElementById(`${prefix}Toggle`)?.addEventListener('click', () => this.toggleVoice());
        document.getElementById(`${prefix}Test`)?.addEventListener('click', () => this.speak('Voz IA ativada. Mensagens educativas, nao recomendacao financeira.', 'test'));
        document.getElementById(`${prefix}Stop`)?.addEventListener('click', () => this.stopSpeaking());
        document.getElementById(`${prefix}Volume`)?.addEventListener('input', (event) => this.setVoiceSettings({ volume: Number(event.target.value) }));
        document.getElementById(`${prefix}Rate`)?.addEventListener('input', (event) => this.setVoiceSettings({ rate: Number(event.target.value) }));
        document.getElementById(`${prefix}Select`)?.addEventListener('change', (event) => this.setVoiceSettings({ voiceName: event.target.value }));
        this.renderVoiceSelect(prefix);
        this.updateStatus(prefix);
    }

    speak(message, priority = 'normal') {
        if (!this.enabled && priority !== 'test') return false;
        if (!('speechSynthesis' in window) || !message) return false;
        const eventType = this.eventTypeFromMessage(message, priority);
        if (priority !== 'test' && !this.shouldSpeak(eventType, message)) return false;

        const utterance = new SpeechSynthesisUtterance(message);
        utterance.lang = this.lang;
        utterance.volume = Math.max(0, Math.min(1, this.volume));
        utterance.rate = Math.max(0.6, Math.min(1.6, this.rate));
        const selectedVoice = this.voices.find((voice) => voice.name === this.voiceName) || this.voices.find((voice) => voice.lang === this.lang);
        if (selectedVoice) utterance.voice = selectedVoice;

        if (priority === 'high' || priority === 'test') window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
        this.lastMessage = message;
        this.lastSpoken.set(eventType, Date.now());
        this.updateStatus();
        return true;
    }

    stopSpeaking() {
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    }

    toggleVoice() {
        this.enabled = !this.enabled;
        this.saveSettings();
        this.updateStatus();
        if (this.enabled) this.speak('Voz IA ativada.', 'test');
        return this.enabled;
    }

    setVoiceSettings(settings = {}) {
        if (settings.volume != null) this.volume = Number(settings.volume);
        if (settings.rate != null) this.rate = Number(settings.rate);
        if (settings.voiceName != null) this.voiceName = settings.voiceName;
        this.saveSettings();
        this.updateStatus();
    }

    shouldSpeak(eventType, message) {
        const last = this.lastSpoken.get(eventType) || 0;
        if (Date.now() - last < this.cooldownMs) return false;
        if (this.lastMessage === message && Date.now() - last < this.cooldownMs * 2) return false;
        return true;
    }

    formatOperationalMessage(signal = {}) {
        const status = String(signal.status || signal.state || '').toLowerCase();
        const direction = String(signal.direction || signal.probable_direction || '').toUpperCase();
        if (status.includes('invalid')) return 'Cenario invalidado.';
        if (status.includes('stopped')) return 'Stop loss atingido.';
        if (status.includes('tp')) return 'Take profit atingido.';
        if (direction === 'BUY' && (status.includes('confirmed') || status.includes('active'))) return 'Compra confirmada.';
        if (direction === 'SELL' && (status.includes('confirmed') || status.includes('active'))) return 'Venda confirmada.';
        return signal.message || signal.technical_reason || '';
    }

    speakLiveStatus(status = {}) {
        const state = status.state;
        const map = {
            ANALYZING: 'Analisando mercado.',
            WAITING_CONFIRMATION: 'Aguardando confirmacao.',
            WEAK_VOLUME: 'Volume fraco. Nao entrar ainda.',
            AGGRESSIVE_ENTRY: 'Entrada agressiva possivel.',
            CONSERVATIVE_ENTRY: 'Entrada conservadora possivel.',
            BUY_CONFIRMED: 'Compra confirmada.',
            SELL_CONFIRMED: 'Venda confirmada.',
            INVALIDATED: 'Cenario invalidado.',
            HIGH_RISK: 'Alto risco. Nao entrar ainda.',
            WAIT_NEXT_CANDLE: 'Aguardar novo candle.',
        };
        const message = map[state];
        if (message) this.speak(message, ['BUY_CONFIRMED', 'SELL_CONFIRMED', 'INVALIDATED', 'HIGH_RISK'].includes(state) ? 'high' : 'normal');
    }

    speakSignal(signal = {}) {
        const message = this.formatOperationalMessage(signal);
        if (!message) return;
        const status = String(signal.status || '').toLowerCase();
        const priority = ['invalidated', 'stopped', 'tp1_hit', 'tp2_hit', 'tp3_hit', 'confirmed', 'active'].includes(status) ? 'high' : 'normal';
        this.speak(message, priority);
    }

    eventTypeFromMessage(message, priority) {
        const normalized = String(message).toLowerCase();
        if (normalized.includes('compra')) return 'buy_confirmed';
        if (normalized.includes('venda')) return 'sell_confirmed';
        if (normalized.includes('invalid')) return 'invalidated';
        if (normalized.includes('take')) return 'take_profit';
        if (normalized.includes('stop')) return 'stop_loss';
        if (normalized.includes('volume fraco')) return 'weak_volume';
        if (normalized.includes('rompimento')) return 'breakout';
        if (normalized.includes('agressiva')) return 'aggressive_entry';
        if (normalized.includes('novo candle')) return 'wait_next_candle';
        return priority || 'normal';
    }

    renderVoiceSelect(prefix = 'voice') {
        const select = document.getElementById(`${prefix}Select`);
        if (!select) return;
        const current = this.voiceName;
        select.innerHTML = this.voices.map((voice) => `<option value="${voice.name}">${voice.name} · ${voice.lang}</option>`).join('');
        if (current && this.voices.some((voice) => voice.name === current)) select.value = current;
    }

    updateStatus(prefix = 'voice') {
        const status = document.getElementById(`${prefix}Status`);
        const last = document.getElementById(`${prefix}LastMessage`);
        const toggle = document.getElementById(`${prefix}Toggle`);
        const volume = document.getElementById(`${prefix}Volume`);
        const rate = document.getElementById(`${prefix}Rate`);
        if (status) status.textContent = this.enabled ? 'ATIVA' : 'DESLIGADA';
        if (last) last.textContent = this.lastMessage || '--';
        if (toggle) toggle.textContent = this.enabled ? 'Desativar voz' : 'Ativar voz';
        if (volume) volume.value = this.volume;
        if (rate) rate.value = this.rate;
    }
}

window.financeVoiceAssistant = window.financeVoiceAssistant || new FinanceVoiceAssistant();
