// ========================================
// INICIALIZAÇÃO DO DASHBOARD
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
});

function initializeDashboard() {
    setupEventListeners();
    setupChartInteractions();
    setupSidebar();
    updateMarketData();
    startRealTimeUpdates();
}

// ========================================
// EVENT LISTENERS
// ========================================

function setupEventListeners() {
    // Seletor de ativo
    const assetSelect = document.getElementById('assetSelect');
    if (assetSelect) {
        assetSelect.addEventListener('change', handleAssetChange);
    }
    
    // Seletor de timeframe
    const timeframeInputs = document.querySelectorAll('input[name="timeframe"]');
    timeframeInputs.forEach(input => {
        input.addEventListener('change', handleTimeframeChange);
    });
    
    // Botões de ação
    const btnRefresh = document.getElementById('btnRefresh');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', handleRefresh);
    }
    
    const btnAlert = document.getElementById('btnAlert');
    if (btnAlert) {
        btnAlert.addEventListener('click', handleNewAlert);
    }
    
    // Navegação lateral
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', handleNavigation);
    });
    
    // Controles de gráfico
    const chartControls = document.querySelectorAll('.btn-icon-small');
    chartControls.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            chartControls.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

// ========================================
// HANDLERS DE EVENTOS
// ========================================

function handleAssetChange(e) {
    const asset = e.target.value;
    const pageTitle = document.querySelector('.page-title');
    if (pageTitle) {
        pageTitle.textContent = `Análise - ${asset}`;
    }
    
    // Atualizar título do gráfico
    const chartHeader = document.querySelector('.chart-header h3');
    if (chartHeader) {
        chartHeader.textContent = `Gráfico - ${asset}`;
    }
    
    console.log('Ativo selecionado:', asset);
    // Aqui você pode fazer uma requisição para obter dados do novo ativo
}

function handleTimeframeChange(e) {
    const timeframe = e.target.value;
    console.log('Timeframe selecionado:', timeframe);
    
    // Adicionar animação de carregamento
    const chartContainer = document.querySelector('.chart-container');
    if (chartContainer) {
        chartContainer.style.opacity = '0.6';
        setTimeout(() => {
            chartContainer.style.opacity = '1';
        }, 300);
    }
}

function handleRefresh() {
    const btn = document.getElementById('btnRefresh');
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Atualizando...';
        
        setTimeout(() => {
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> Atualizar';
            showNotification('Dados atualizados com sucesso!', 'success');
        }, 1000);
    }
}

function handleNewAlert() {
    showNotification('Diálogo de novo alerta será aberto', 'info');
    // Aqui você pode abrir um modal para criar novo alerta
}

function handleNavigation(e) {
    e.preventDefault();
    
    // Remover classe active de todos os itens
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Adicionar classe active ao item clicado
    this.classList.add('active');
    
    const page = this.getAttribute('data-page');
    console.log('Navegando para:', page);
    
    // Fechar sidebar em mobile
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && window.innerWidth <= 768) {
        sidebar.classList.remove('active');
    }
}

// ========================================
// SIDEBAR
// ========================================

function setupSidebar() {
    const toggleBtn = document.getElementById('toggleSidebar');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.toggle('active');
        });
    }
    
    // Fechar sidebar ao clicar fora
    document.addEventListener('click', function(e) {
        const sidebar = document.querySelector('.sidebar');
        const toggleBtn = document.getElementById('toggleSidebar');
        
        if (sidebar && toggleBtn && window.innerWidth <= 768) {
            if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        }
    });
}

// ========================================
// ATUALIZAÇÕES EM TEMPO REAL
// ========================================

function startRealTimeUpdates() {
    // Atualizar preços a cada 5 segundos
    setInterval(updateMarketData, 5000);
    
    // Atualizar sinais a cada 30 segundos
    setInterval(updateSignals, 30000);
    
    // Atualizar alertas a cada 10 segundos
    setInterval(updateAlerts, 10000);
}

function updateMarketData() {
    const cards = document.querySelectorAll('.market-card');
    
    cards.forEach(card => {
        // Simular atualização de preço
        const priceElement = card.querySelector('.card-price');
        if (priceElement) {
            const currentPrice = parseFloat(priceElement.textContent.replace('R$ ', '').replace(',', '.'));
            const change = (Math.random() - 0.5) * 0.1;
            const newPrice = (currentPrice + change).toFixed(2);
            priceElement.textContent = `R$ ${newPrice.replace('.', ',')}`;
            
            // Animar mudança
            priceElement.style.color = change > 0 ? 'var(--accent-green)' : 'var(--accent-red)';
            setTimeout(() => {
                priceElement.style.color = 'var(--accent-blue)';
            }, 1000);
        }
    });
}

function updateSignals() {
    console.log('Atualizando sinais...');
    // Aqui você pode fazer uma requisição para atualizar os sinais da IA
}

function updateAlerts() {
    console.log('Atualizando alertas...');
    // Aqui você pode fazer uma requisição para atualizar os alertas
}

// ========================================
// INTERAÇÕES COM GRÁFICO
// ========================================

function setupChartInteractions() {
    // Os controles do gráfico já estão configurados em setupEventListeners
    // Aqui você pode adicionar mais funcionalidades se necessário
    
    // Exemplo: Zoom do gráfico
    setupChartZoom();
}

function setupChartZoom() {
    const chartContainer = document.querySelector('.chart-container');
    if (chartContainer) {
        // Implementar zoom com mouse wheel
        chartContainer.addEventListener('wheel', function(e) {
            e.preventDefault();
            // Lógica de zoom aqui
            console.log('Zoom do gráfico');
        });
    }
}

// ========================================
// NOTIFICAÇÕES
// ========================================

function showNotification(message, type = 'info') {
    // Criar elemento de notificação
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: ${getNotificationColor(type)};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 2000;
        animation: slideIn 0.3s ease;
        max-width: 400px;
        font-size: 14px;
    `;
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Remover após 3 segundos
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function getNotificationColor(type) {
    const colors = {
        success: '#10b981',
        error: '#ef4444',
        warning: '#f59e0b',
        info: '#00d4ff'
    };
    return colors[type] || colors.info;
}

// ========================================
// ANIMAÇÕES CSS
// ========================================

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }
    
    .fa-spin {
        animation: spin 1s linear infinite;
    }
`;
document.head.appendChild(style);

// ========================================
// RESPONSIVIDADE
// ========================================

let resizeTimer;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {
        handleWindowResize();
    }, 250);
});

function handleWindowResize() {
    // Ajustar layout responsivo
    const width = window.innerWidth;
    const sidebar = document.querySelector('.sidebar');
    
    if (width > 768) {
        if (sidebar) {
            sidebar.classList.remove('active');
        }
    }
}

// ========================================
// TEMA ESCURO/CLARO
// ========================================

function setupTheme() {
    const themeToggle = document.querySelector('.fa-moon').parentElement;
    
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('light-mode');
            
            // Salvar preferência
            const isLightMode = document.body.classList.contains('light-mode');
            localStorage.setItem('theme', isLightMode ? 'light' : 'dark');
        });
    }
    
    // Carregar tema salvo
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
    }
}

// ========================================
// BUSCA
// ========================================

function setupSearch() {
    const searchInput = document.querySelector('.search-box input');
    
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase();
            console.log('Buscando:', query);
            
            // Aqui você pode implementar a busca de ativos
        });
    }
}

// ========================================
// INICIALIZAR FUNCIONALIDADES ADICIONAIS
// ========================================

setupTheme();
setupSearch();

// ========================================
// DADOS DE EXEMPLO
// ========================================

const mockData = {
    assets: [
        { symbol: 'PETR4', price: 28.35, change: 2.45, high: 29.50, low: 27.80, volume: '2.5M' },
        { symbol: 'VALE3', price: 56.78, change: -1.23, high: 58.20, low: 56.10, volume: '1.8M' },
        { symbol: 'WEGE3', price: 42.15, change: 3.12, high: 43.80, low: 40.90, volume: '3.2M' },
        { symbol: 'ITUB4', price: 35.45, change: 1.80, high: 36.20, low: 35.00, volume: '2.1M' }
    ],
    signals: [
        { type: 'buy', confidence: 92, time: '2 minutos' },
        { type: 'sell', confidence: 78, time: '15 minutos' },
        { type: 'hold', confidence: 65, time: '45 minutos' }
    ]
};

// ========================================
// FUNÇÕES AUXILIARES
// ========================================

function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

function formatPercent(value) {
    return (value > 0 ? '+' : '') + value.toFixed(2) + '%';
}

function getAssetColor(change) {
    return change > 0 ? 'var(--accent-green)' : 'var(--accent-red)';
}

// ========================================
// LOG
// ========================================

console.log('%cDashboard IA v1.0', 'color: #00d4ff; font-size: 16px; font-weight: bold;');
console.log('%cSistema de Análise Financeira com IA', 'color: #a0aec0; font-size: 12px;');
