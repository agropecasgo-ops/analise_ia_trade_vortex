# 🚀 Sistema Profissional de Análise Operacional com IA

Sistema completo de trading com **análise técnica profissional**, **IA geradora de sinais**, **gráficos candlestick** com TradingView Lightweight Charts, e **backtest automático**.

> **Dashboard Avançado**: http://localhost:5000/advanced

---

## ⚡ Quick Start (30 segundos)

```powershell
cd "c:\Users\migue\Documents\Analise Inteligente\PROGETO IA"
python run.py
# Escolher opção 2: Dashboard Profissional
# Abrir: http://localhost:5000/advanced
```

---

## 📊 O que Tem de Novo?

### ✨ Dashboard Profissional
- ✅ Gráfico Candlestick com **TradingView Lightweight Charts**
- ✅ Análise **Multi-Timeframe** (1h, 4h, 1d)
- ✅ **Score Operacional** em tempo real (0-100)
- ✅ **Heatmap de tendência** (8 ativos × 3 timeframes)
- ✅ **Backtest automático** de estratégias
- ✅ Visual premium estilo corretora profissional

### 🧠 Sistema de IA Avançado
- **7 tipos de sinais**: Compra/Venda Agressiva, Conservadora, Neutra
- **Score de confiança** de 0-100
- **Justificativa automática** textual
- **Análise Risco/Retorno** com Stop Loss + 2 Alvos
- **Suporte/Resistência automático**

### 📈 Análise Técnica Profissional
- **Indicadores**: RSI, MACD, Bandas Bollinger, ATR
- **Médias móveis**: EMA20, EMA50, SMA200
- **Padrões**: Doji, Martelo, Enforcado
- **Volume**: Análise integrada

### 📊 Backtesting
- Teste de estratégias automático
- Taxa de acerto, retorno total, fator lucro
- Curva de capital histórica

---

## 📁 Arquitetura

```
PROGETO IA/
│
├── 🐍 app.py                      # Flask + 7 rotas API
├── ⚙️  config.py                  # Configurações centralizadas
├── 📦 requirements.txt            # Dependências
│
├── 📁 ia/                         # Módulo IA (500+ linhas)
│   ├── analysis.py                # Motor de análise técnica
│   └── data_generator.py          # Dados históricos
│
├── 📁 templates/
│   ├── base.html                  # Template base
│   ├── index.html                 # Dashboard simples
│   └── advanced.html              # Dashboard profissional ⭐
│
├── 📁 static/
│   ├── css/
│   │   ├── style.css              # Estilos TradingView
│   │   └── advanced.css           # Estilos profissionais
│   └── js/
│       ├── dashboard.js           # JS base
│       └── advanced-dashboard.js  # JS com TradingView Charts
│
├── 📄 ADVANCED_README.md          # Doc técnica (completa)
├── 📄 QUICK_START.md              # Guia prático
├── 📄 API_EXAMPLES.json           # Exemplos API
├── 🧪 test_system.py              # Testes automatizados
└── 🚀 run.py                      # Inicializador com menu
```

---

## 🎯 Como Usar

### 1. Iniciar Aplicação

```powershell
# Opção A: Menu interativo
python run.py
# Escolher 2

# Opção B: Direto
python app.py
# Acessar: http://localhost:5000/advanced
```

### 2. Navegar no Dashboard

1. **Selecione ativo** (PETR4, VALE3, etc)
2. **Escolha timeframe** (1h, 4h, 1d)
3. **Leia o sinal** central
4. **Verifique risco/retorno**
5. **Valide multi-timeframe**
6. **Leia justificativa**
7. **Execute backtest (opcional)**

### 3. Entender Sinais

| Sinal | Emoji | Confiança | O Que Fazer |
|-------|-------|-----------|------------|
| Compra Agressiva | 🟢🚀 | 80%+ | Entrar volume |
| Compra Conservadora | 🟢 | 60-80% | Entrar pequeno |
| Compra | ➕ | 40-60% | Aguardar |
| Neutro | ⚪ | <50% | Ficar fora |
| Venda | ➖ | 40-60% | Sair |
| Venda Agressiva | 🔴🚀 | 80%+ | Sair já |

---

## 🔌 API Endpoints

### Análise
```
GET /api/analysis/<symbol>/<timeframe>
  Retorna: sinal, score, indicadores, níveis
  
GET /api/multi-timeframe/<symbol>
  Retorna: análise consolidada (1h + 4h + 1d)
  
GET /api/heatmap
  Retorna: grid 8 ativos × 3 timeframes
```

### Dados
```
GET /api/candles/<symbol>/<timeframe>
GET /api/assets
GET /api/timeframes
```

### Estratégias
```
GET /api/backtest/<symbol>
  Retorna: trades, taxa acerto, retorno
```

**Exemplo**:
```bash
curl http://localhost:5000/api/analysis/PETR4/1h
```

Ver **API_EXAMPLES.json** para detalhes.

---

## 📊 Score Operacional

Escala **0-100** que considera:

| Fator | Peso | Como Funciona |
|-------|------|---------------|
| **Tendência** | 35% | EMA20 > EMA50 > SMA200 = +35 |
| **MACD** | 30% | Bullish = +30, Bearish = -30 |
| **RSI** | 20% | <30 = +15, >70 = -15 |
| **Volume** | 10% | Alto = +10 |
| **Padrões** | 5% | Identificado = +5 |

**Interpretação**:
- **75-100**: Operação excelente ✅
- **50-74**: Operação válida ✅
- **25-49**: Questionável ⚠️
- **0-24**: Evitar ❌

---

## 📚 Documentação

| Arquivo | Conteúdo |
|---------|----------|
| **[QUICK_START.md](QUICK_START.md)** | Guia prático rápido |
| **[ADVANCED_README.md](ADVANCED_README.md)** | Documentação técnica completa |
| **[API_EXAMPLES.json](API_EXAMPLES.json)** | Exemplos de requisições |
| **ia/analysis.py** | Código fonte comentado |

---

## 🧪 Testes

```powershell
python test_system.py

Executa:
 ✓ Análise técnica completa
 ✓ Geração de sinais
 ✓ Risco/Retorno
 ✓ Score operacional
 ✓ Backtest
 ✓ Multi-ativo
```

---

## 🎨 Design

- **Tema Escuro**: Estilo TradingView profissional
- **Responsivo**: Desktop, tablet, mobile
- **Animações**: Transições fluidas
- **Cores Significativas**:
  - 🟢 Verde = Compra/Alta
  - 🔴 Vermelho = Venda/Baixa
  - ⚪ Cinza = Neutro
  - 🔵 Azul = Dados

---

## ⚙️ Configurações

Edite **config.py**:

```python
# Indicadores
INDICATORS['RSI']['period'] = 14
INDICATORS['MACD']['fast'] = 12

# Risco
RISK_MANAGEMENT['atr_multiplier_stop'] = 1.5

# Backtest
BACKTEST['initial_capital'] = 10000
```

---

## 📦 Dependências

```
Flask==2.3.3
pandas==2.0.3
numpy==1.24.3
python-dotenv==1.0.0
```

**Instalar**:
```powershell
pip install -r requirements.txt
```

---

## 🚀 Funcionalidades

### ✅ Implementadas
- [x] Gráfico Candlestick profissional
- [x] 7 tipos de sinais
- [x] Score operacional (0-100)
- [x] Análise multi-timeframe
- [x] Risco/Retorno automático
- [x] Suporte/Resistência
- [x] Heatmap tendência
- [x] Backtest estratégias
- [x] Justificativa IA
- [x] Dashboard responsivo

### 🔄 Planejadas
- [ ] APIs de corretoras (B3, ATIVA, etc)
- [ ] Alertas Telegram/Email
- [ ] Histórico operações
- [ ] Gerenciador carteira
- [ ] Trading automático
- [ ] ML avançado
- [ ] App mobile

---

## 💡 Exemplos

### ✅ Operação Perfeita
```
PETR4 | 1h | Score: 92/100
Sinal: COMPRA AGRESSIVA (95% confiança)
Multi-TF: 1h=COMPRA ✓ | 4h=COMPRA ✓ | 1d=ALTA ✓
R/R: 1:1.8
→ OPERAR COM CONFIANÇA
```

### ⚠️ Operação Questionável
```
VALE3 | 4h | Score: 45/100
Sinal: NEUTRO (52% confiança)
Multi-TF: 1h=COMPRA | 4h=NEUTRO ✗ | 1d=VENDA
R/R: 1:0.8
→ AGUARDAR MELHOR OPORTUNIDADE
```

---

## 🎯 Ativos Suportados

- PETR4 - Petrobras
- VALE3 - Vale
- WEGE3 - Weg
- ITUB4 - Itaú
- BBDC4 - Bradesco
- ABEV3 - Ambev
- JBSS3 - JBS
- RENT3 - Localiza

---

## ⚠️ Avisos

1. **Dados simulados** (para reais, conectar corretora)
2. **Educacional** (usar demo primeiro)
3. **Não é conselho** (validar fundamental)
4. **Risco real** (trading pode perder capital)
5. **Sempre backtest** (antes de operar)

---

## 🔍 Troubleshooting

| Problema | Solução |
|----------|---------|
| Gráfico não carrega | F5, aguardar 5s, trocar ativo |
| Lentidão | Fechar abas, Ctrl+Shift+Del |
| Dados estranhos | Normal - são dados simulados |
| API error | F12 console, reiniciar |

---

## 📈 Próximos Passos

1. ✅ Instalar e executar
2. ✅ Explorar dashboard
3. ✅ Entender sinais
4. ✅ Rodar backtest
5. ✅ Fazer testes

---

**Versão**: 2.0 (Profissional)  
**Data**: Maio 2026  
**Status**: ✅ Pronto para Uso  
**Desenvolvido com**: Flask, Python, TradingView Lightweight Charts

🚀 **Bom trading!**
