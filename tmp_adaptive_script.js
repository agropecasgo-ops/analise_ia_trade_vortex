function renderAdaptiveStatus(data) {
        const strong = Array.isArray(data.strongContexts) ? data.strongContexts : [];
        const weak = Array.isArray(data.weakContexts) ? data.weakContexts : [];
        const bestTimeframes = Array.isArray(data.bestTimeframes) ? data.bestTimeframes : [];
        const bestAssets = Array.isArray(data.bestAssets) ? data.bestAssets : [];
        const recommendation = data.adaptiveRecommendation || {};
        const contextual = data.winRateContextual || {};
        const contextCount = Object.values(contextual).reduce((total, group) => total + Object.keys(group || {}).length, 0);

        text("adaptiveStatusTag", data.success ? "Adaptativo ativo" : "Adaptivo indisponivel");
        text("adaptiveContextsAnalyzed", contextCount ? `${contextCount} contextos` : "--");
        text("adaptiveRecommendationCount", recommendation.details ? `${recommendation.details.length} recomendações` : "--");
        text("adaptiveStrongCount", strong.length ? `${strong.length} fortes` : "--");
        text("adaptiveWeakCount", weak.length ? `${weak.length} fracos` : "--");

        renderAdaptiveChips("adaptiveBestTimeframesList", bestTimeframes.slice(0, 6), "buy", (item) => item.timeframe || item.key || "--", (item) => `${Math.round(item.winRate || 0)}%`);
        renderAdaptiveChips("adaptiveBestAssetsList", bestAssets.slice(0, 6), "neutral", (item) => item.asset || item.key || "--", (item) => `${Math.round(item.winRate || 0)}%`);
        renderAdaptiveChips("adaptiveStrongContexts", strong.slice(0, 6), "buy", (item) => `${item.dimension}:${item.value}`, (item) => `${Math.round(item.winRate || 0)}%`);
        renderAdaptiveChips("adaptiveWeakContexts", weak.slice(0, 6), "caution", (item) => `${item.dimension}:${item.value}`, (item) => `${Math.round(item.winRate || 0)}%`);

        const summary = recommendation.summary || "Sem recomendações adaptativas robustas no momento.";
        const detailItems = Array.isArray(recommendation.details) ? recommendation.details : [];
        const detailChips = detailItems.slice(0, 4).map((item) => `<span class="adaptive-chip ${escapeHtml(item.type || 'neutral')}">${escapeHtml(item.message || item.summary || 'Detalhe')}</span>`).join("");
        $("adaptiveRecommendation").innerHTML = `
            <strong>Resumo adaptativo</strong>
            <div>${escapeHtml(summary)}</div>
            <div class="adaptive-chip-list">${detailChips}</div>
        `;
    }

    function renderAdaptiveChips(id, items, tone, labelFn = (item) => item.label || item.name || item.timeframe || item.asset || item.value || "--", extraFn = () => "") {
        const container = $(id);
        if (!container) return;
        if (!items.length) {
            container.innerHTML = `<span class="adaptive-chip ${tone}">Sem dados suficientes</span>`;
            return;
        }
        container.innerHTML = items
            .map((item) => {
                const label = escapeHtml(String(labelFn(item) || "--"));
                const extra = escapeHtml(String(extraFn(item) || ""));
                return `<span class="adaptive-chip ${tone}">${label}${extra ? ` · ${extra}` : ""}</span>`;
            })
            .join("");
    }

    async function loadAdaptiveStatus() {
        try {
            const response = await fetch("/api/institutional/adaptive-status?limit=300");
            const data = await response.json();
            renderAdaptiveStatus(data);
        } catch (error) {
            renderAdaptiveStatus({});
        }
    }

    