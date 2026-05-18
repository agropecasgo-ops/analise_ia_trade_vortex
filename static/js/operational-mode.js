(function () {
    const storageKey = 'financeai.operationalMode';
    const modes = new Set(['conservador', 'moderado', 'agressivo']);

    function normalize(value) {
        const mode = String(value || 'moderado').trim().toLowerCase();
        return modes.has(mode) ? mode : 'moderado';
    }

    function get() {
        const legacyMode = localStorage.getItem('financeai.flow.operationalMode')
            || localStorage.getItem('financeai.institutional.operationalMode');
        return normalize(localStorage.getItem(storageKey) || sessionStorage.getItem(storageKey) || legacyMode);
    }

    function syncSelects(mode) {
        document.querySelectorAll('[data-operational-mode-select]').forEach((select) => {
            if (select.value !== mode) select.value = mode;
        });
        document.documentElement.dataset.operationalMode = mode;
    }

    function set(value, options = {}) {
        const mode = normalize(value);
        localStorage.setItem(storageKey, mode);
        sessionStorage.setItem(storageKey, mode);
        syncSelects(mode);
        if (!options.silent) {
            window.dispatchEvent(new CustomEvent('financeai:operational-mode-change', { detail: { mode } }));
        }
        return mode;
    }

    function onChange(callback) {
        if (typeof callback !== 'function') return () => {};
        const handler = (event) => callback(normalize(event.detail?.mode));
        window.addEventListener('financeai:operational-mode-change', handler);
        return () => window.removeEventListener('financeai:operational-mode-change', handler);
    }

    window.FinanceOperationalMode = { get, set, onChange, normalize, storageKey };

    document.addEventListener('DOMContentLoaded', () => {
        const mode = set(get(), { silent: true });
        document.querySelectorAll('[data-operational-mode-select]').forEach((select) => {
            select.value = mode;
            select.addEventListener('change', () => set(select.value));
        });
    });
})();
