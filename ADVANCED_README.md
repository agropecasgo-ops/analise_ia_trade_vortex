# Sistema Profissional de Análise Operacional com IA

Sistema avançado de trading com análise técnica profissional, geração automática de sinais de IA e backtest de estratégias.

## 🚀 Características Principais

### Dashboard Profissional
- **Gráfico Candlestick** com TradingView Lightweight Charts
- **Múltiplos Timeframes**: 1h, 4h, 1d
- **Análise Multi-Timeframe**: sincronização entre timeframes
- **Tema Escuro Premium**: estilo TradingView profissional
- **Interface Responsiva**: desktop, tablet e mobile

### Análise Técnica Avançada
- **Indicadores Integrados**:
  - RSI (Índice de Força Relativa)
  - MACD (Moving Average Convergence Divergence)
  - Bandas de Bollinger
  - ATR (Average True Range)
  - EMA/SMA (Médias Móveis)

- **Análise de Padrões**:
  - Doji
  - Martelo
  - Enforcado
  - Reconhecimento automático

- **Suporte e Resistência**:
  - Identificação automática de níveis
  - Cálculo de proximidade percentual
  - Histórico visual

### Sistema de Sinais IA

A inteligência artificial gera sinais classificados em 7 categorias:

1. **COMPRA AGRESSIVA** (Score > 0.5)
   - Múltiplos indicadores bullish confirmados
   - Confiança muito alta

2. **COMPRA CONSERVADORA** (Score 0.3-0.5)
   - Sinais mistos mas tendência positiva
   - Entrada com cuidado

3. **COMPRA** (Score 0.1-0.3)
   - Oportunidade moderada
   - Validação adicional recomendada

4. **NEUTRO** (Score -0.1 a 0.1)
   - Sem direção clara
   - Aguardar confirmação

5. **VENDA** (Score -0.3 a -0.1)
   - Oportunidade de venda moderada

6. **VENDA AGRESSIVA** (Score < -0.5)
   - Múltiplos sinais bearish
   - Saída imediata recomendada

7. **CONFIRMAÇÃO DE TENDÊNCIA**
   - Validação de continuação
   - Reforço da direção atual

### Score Operacional

Escala 0-100 que considera:
- **Tendência (35%)**: análise multi-timeframe
- **MACD (30%)**: convergência/divergência
- **RSI (20%)**: overbought/oversold
- **Volume (10%)**: confirmação do movimento
- **Padrões (5%)**: reconhecimento automático

Interpretação:
- 75-100: Operação Muito Boa
- 50-74: Operação Válida
- 25-49: Operação Questionável
- 0-24: Evitar Operação

### Risco e Gerenciamento

Para cada sinal, o sistema calcula automaticamente:

- **Entrada**: Preço de entrada recomendado
- **Stop Loss**: Nível de proteção (ATR × 1.5)
- **Alvo 1**: Retorno 1:1 (risco = retorno)
- **Alvo 2**: Retorno 1:2 (retorno 2× o risco)
- **Razão R/R**: Índice risco/retorno

### Heatmap de Tendência

Visualização em grid mostrando:
- **Ativos**: 8 principais ações do mercado
- **Timeframes**: 1h, 4h, 1d
- **Cores**:
  - 🟢 Verde: Compra (entrada agressiva/conservadora)
  - ⚪ Cinza: Neutro
  - 🔴 Vermelho: Venda

### Backtest de Estratégias

Motor de backtest integrado que testa:
- Estratégia de Cruzamento de Médias Móveis
- Período: 180 dias (configurável)
- Capital inicial: R$ 10.000

Métricas retornadas:
- Total de trades
- Taxa de acerto (%)
- Retorno total (%)
- Fator de lucro

### Justificativa Automática da IA

Para cada sinal, o sistema gera justificativa textual:
- Análise de tendência
- Status do RSI
- Convergência MACD
- Confirmação de volume
- Padrões identificados

## 📋 Estrutura do Projeto

```
PROGETO IA/
├── app.py                    # Aplicação Flask principal
├── requirements.txt          # Dependências Python
├── ia/
│   ├── __init__.py
│   ├── analysis.py          # Motor de análise técnica
│   └── data_generator.py    # Gerador de dados históricos
├── templates/
│   ├── base.html            # Template base
│   ├── index.html           # Dashboard simples
│   └── advanced.html        # Dashboard profissional
├── static/
│   ├── css/
│   │   ├── style.css        # Estilos base
│   │   └── advanced.css     # Estilos avançados
│   └── js/
│       ├── dashboard.js     # JS base
│       └── advanced-dashboard.js  # JS avançado
```

## 🛠 Instalação

### 1. Clonar/Baixar o Projeto
```bash
cd "c:\Users\migue\Documents\Analise Inteligente\PROGETO IA"
```

### 2. Criar Ambiente Virtual
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Executar a Aplicação
```bash
python app.py
```

### 5. Acessar
- Dashboard Simples: http://localhost:5000
- Dashboard Profissional: http://localhost:5000/advanced

## 📊 Rotas da API

### Dados
```
GET /api/candles/<symbol>/<timeframe>
GET /api/assets
GET /api/timeframes
```

### Análise
```
GET /api/analysis/<symbol>/<timeframe>
GET /api/multi-timeframe/<symbol>
GET /api/heatmap
GET /api/backtest/<symbol>
```

Exemplo de requisição:
```bash
curl http://localhost:5000/api/analysis/PETR4/1h
```

## 🎯 Ativos Suportados

- PETR4 - Petrobras
- VALE3 - Vale
- WEGE3 - Weg
- ITUB4 - Itaú
- BBDC4 - Banco Bradesco
- ABEV3 - Ambev
- JBSS3 - JBS
- RENT3 - Localiza

## ⏰ Timeframes Disponíveis

- 1h - 1 hora
- 4h - 4 horas
- 1d - 1 dia

## 🧠 Lógica da IA

### Componentes do Sinal

1. **RSI Signal** (20% peso)
   - Sobrevenda (< 30): +15 pontos
   - Sobrecompra (> 70): -15 pontos

2. **MACD Signal** (30% peso)
   - Bullish (acima): +30 pontos
   - Bearish (abaixo): -30 pontos

3. **Trend Signal** (35% peso)
   - Uptrend: +35 pontos
   - Downtrend: -35 pontos
   - Sideways: 0 pontos

4. **Volume Signal** (10% peso)
   - Alto: +10 pontos
   - Normal: +6 pontos
   - Baixo: 0 pontos

5. **Pattern Signal** (5% peso)
   - Padrão identificado: +5 pontos

### Cálculo Final

Score = Soma ponderada dos componentes

Signal Type baseado no Score:
- Score > 0.5: Entrada Agressiva (Compra forte)
- Score > 0.3: Entrada Conservadora (Compra)
- Score > 0.1: Compra (Sinal positivo)
- Score < -0.5: Venda Agressiva
- Score < -0.3: Venda
- Caso contrário: Neutro

## 💡 Dicas de Uso

1. **Análise Multi-Timeframe**: Use os 3 timeframes juntos
   - 1h: operação de curto prazo
   - 4h: confirmação de médio prazo
   - 1d: validação de longo prazo

2. **Score Operacional**: Priorize operações com score > 70

3. **Risco/Retorno**: Sempre respeite os níveis de stop/alvo

4. **Backtest**: Execute antes de operar uma estratégia

5. **Justificativa**: Leia sempre a explicação dos sinais

## 🔄 Atualizações em Tempo Real

O sistema atualiza dados a cada:
- **5 segundos**: Preços
- **30 segundos**: Sinais
- **1 minuto**: Gráficos

## ⚠️ Avisos Importantes

Este é um sistema de **análise técnica** baseado em histórico. Para usar em operações reais:

1. ✅ Validar com análise fundamental
2. ✅ Usar em conta demo primeiro
3. ✅ Começar com operações pequenas
4. ✅ Seguir rigorosamente risco/retorno
5. ✅ Acompanhar notícias do mercado

## 📈 Funcionalidades Futuras

- [ ] Integração com APIs de corretoras
- [ ] Alertas por email/Telegram
- [ ] Histórico de operações
- [ ] Simulador de carteira
- [ ] Análise de múltiplos ativos simultâneos
- [ ] Dashboard mobile nativo
- [ ] Exportação de relatórios PDF

## 🤝 Suporte

Para dúvidas ou sugestões, consulte a documentação do código ou revise as análises geradas.

## 📄 Licença

Uso privado e educacional.

---

**Versão**: 1.0  
**Última Atualização**: Maio 2026  
**Desenvolvido com**: Flask, Python, TradingView Lightweight Charts
