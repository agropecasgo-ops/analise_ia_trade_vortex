(function () {
    const replacements = [
        [/Ã¡/g, 'á'], [/Ã /g, 'à'], [/Ã¢/g, 'â'], [/Ã£/g, 'ã'], [/Ã©/g, 'é'],
        [/Ãª/g, 'ê'], [/Ã­/g, 'í'], [/Ã³/g, 'ó'], [/Ã´/g, 'ô'], [/Ãµ/g, 'õ'],
        [/Ãº/g, 'ú'], [/Ã§/g, 'ç'], [/Â·/g, '·'], [/Âº/g, 'º'],
        [/\banalise\b/gi, 'análise'],
        [/\banalises\b/gi, 'análises'],
        [/\bconfirmacao\b/gi, 'confirmação'],
        [/\bconfirmacoes\b/gi, 'confirmações'],
        [/\btendencia\b/gi, 'tendência'],
        [/\btendencias\b/gi, 'tendências'],
        [/\bdirecao\b/gi, 'direção'],
        [/\bdirecional\b/gi, 'direcional'],
        [/\bexecucao\b/gi, 'execução'],
        [/\brecomendacao\b/gi, 'recomendação'],
        [/\bpossivel\b/gi, 'possível'],
        [/\bpossiveis\b/gi, 'possíveis'],
        [/\bcenario\b/gi, 'cenário'],
        [/\bcenarios\b/gi, 'cenários'],
        [/\bconfluencia\b/gi, 'confluência'],
        [/\bconfluencias\b/gi, 'confluências'],
        [/\bexplicacao\b/gi, 'explicação'],
        [/\bgrafico\b/gi, 'gráfico'],
        [/\bgraficos\b/gi, 'gráficos'],
        [/\bhistorico\b/gi, 'histórico'],
        [/\bestatistica\b/gi, 'estatística'],
        [/\bestatistico\b/gi, 'estatístico'],
        [/\bperiodos\b/gi, 'períodos'],
        [/\bhorarios\b/gi, 'horários'],
        [/\bindisponivel\b/gi, 'indisponível'],
        [/\binvalidacao\b/gi, 'invalidação'],
        [/\breducao\b/gi, 'redução'],
        [/\bpreferencia\b/gi, 'preferência'],
        [/\bpreco\b/gi, 'preço'],
        [/\bproxima\b/gi, 'próxima'],
        [/\bproximo\b/gi, 'próximo'],
        [/\bunico\b/gi, 'único'],
        [/\bforca\b/gi, 'força'],
        [/\bpressao\b/gi, 'pressão'],
        [/\bnao\b/gi, 'não'],
        [/\bapos\b/gi, 'após'],
        [/\bminimo\b/gi, 'mínimo'],
        [/\bmaximo\b/gi, 'máximo'],
        [/\bliquidez detectada\b/gi, 'liquidez detectada'],
        [/\bvolatilidade baixa\b/gi, 'volatilidade baixa'],
    ];

    function matchCase(original, replacement) {
        if (original === original.toUpperCase()) return replacement.toUpperCase();
        if (original[0] === original[0]?.toUpperCase()) {
            return replacement.charAt(0).toUpperCase() + replacement.slice(1);
        }
        return replacement;
    }

    function normalize(value) {
        if (value == null || value === '') return value;
        if (typeof value !== 'string') return value;
        return replacements.reduce((text, [pattern, replacement]) => (
            text.replace(pattern, (match) => matchCase(match, replacement))
        ), value);
    }

    function escape(value) {
        return String(normalize(value) ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function normalizeDocument(root = document.body) {
        if (!root) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                const parent = node.parentElement;
                if (!parent || ['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'OPTION'].includes(parent.tagName)) {
                    return NodeFilter.FILTER_REJECT;
                }
                return node.nodeValue && node.nodeValue.trim()
                    ? NodeFilter.FILTER_ACCEPT
                    : NodeFilter.FILTER_REJECT;
            },
        });
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach((node) => {
            node.nodeValue = normalize(node.nodeValue);
        });
    }

    window.FinanceText = window.FinanceText || {};
    window.FinanceText.normalize = normalize;
    window.FinanceText.escape = escape;
    window.FinanceText.normalizeDocument = normalizeDocument;

    document.addEventListener('DOMContentLoaded', () => normalizeDocument());
})();
