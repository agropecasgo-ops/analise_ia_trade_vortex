# 🚀 Guia Rápido - Dashboard Profissional

## Iniciar em 30 Segundos

### 1. Abrir PowerShell
```powershell
cd "c:\Users\migue\Documents\Analise Inteligente\PROGETO IA"
python run.py
```

### 2. Escolher Opção 2 (Dashboard Profissional)

### 3. Acessar http://localhost:5000/advanced

---

## 📊 Interface Profissional

### Topo
- **Asset Selector**: Escolha o ativo (PETR4, VALE3, WEGE3, etc)
- **Timeframe**: 1h, 4h, 1d
- **Info Display**: Preço atual, variação, score

### Gráfico Candlestick (Centro-Esquerda)
- Gráfico interativo com TradingView Lightweight Charts
- Velas com volume
- Médias móveis (EMA20, EMA50, SMA200)
- Zoom e navegação

### Painel Análise (Direita)
Composto por 4 cards:

#### 1️⃣ Score Operacional
- Escala 0-100
- Gauge visual
- Qualidade da operação

#### 2️⃣ Sinal da IA
- Tipo: COMPRA, VENDA, NEUTRO, etc
- Confiança em %
- Recomendação automática

#### 3️⃣ Risco/Retorno
- Entrada
- Stop Loss
- Alvo 1 (1:1)
- Alvo 2 (1:2)
- Razão R/R

#### 4️⃣ Multi-Timeframe
- Análise em 3 timeframes
- Alinhamento de sinais
- Validação cruzada

### Análise Detalhada (Inferior)

#### Justificativa da IA
Explicação textual do sinal incluindo:
- Tendência
- RSI status
- MACD status
- Volume
- Padrões

#### Suporte e Resistência
Níveis automáticos com:
- Tipo (Suporte/Resistência)
- Preço
- Distância %

#### Indicadores Técnicos
Grade mostrando:
- RSI
- MACD
- ATR
- Volume

#### Heatmap de Tendência
Grid com ativos × timeframes
Cores indicam sinais:
- 🟢 Verde = Compra
- ⚪ Cinza = Neutro
- 🔴 Vermelho = Venda

#### Backtest
Executar backtest da estratégia
Resultados:
- Total de trades
- Taxa de acerto
- Retorno total
- Fator de lucro

---

## 🎯 Como Usar

### 1. Selecionar Ativo
```
Clique em "PETR4" e escolha outro ativo
```

### 2. Escolher Timeframe
```
1h = operação intraday rápida
4h = swing trade
1d = posição média
```

### 3. Ler o Sinal
```
Ver no card central qual é a recomendação
Verificar confiança
```

### 4. Analisar Risco/Retorno
```
Entrada = seu preço de compra
Stop = perde se descer disso
Alvo 1 = primeira venda (lucro mínimo)
Alvo 2 = segunda venda (lucro máximo)
```

### 5. Ler Justificativa
```
Scroll na seção inferior
Entender por que IA fez a recomendação
```

### 6. Validar Multi-Timeframe
```
Ver se os 3 timeframes concordam
Compra forte = todos dizendo COMPRA
```

### 7. Executar Backtest (Opcional)
```
Botão "Executar Backtest"
Ver histórico de rentabilidade
```

---

## 📈 Interpretação dos Sinais

### ✅ COMPRA AGRESSIVA
- Score > 0.5
- Múltiplos indicadores dizem SIM
- Confiança > 80%
- **Ação**: Entrar com volume maior

### ✅ COMPRA CONSERVADORA
- Score 0.3-0.5
- Sinais bons mas não perfeitos
- Confiança 60-80%
- **Ação**: Entrar com volume menor

### ➕ COMPRA
- Score 0.1-0.3
- Sinal positivo mas fraco
- Confiança 40-60%
- **Ação**: Aguardar confirmação

### ⚪ NEUTRO
- Score ~0
- Sem direção clara
- Confiança < 50%
- **Ação**: Ficar fora

### ➖ VENDA
- Score -0.3 a -0.1
- Sinais de venda moderados
- Confiança 40-60%
- **Ação**: Sair ou não entrar

### ✅ VENDA AGRESSIVA
- Score < -0.5
- Múltiplos sinais de VENDA
- Confiança > 80%
- **Ação**: Sair imediatamente

---

## 🎓 Exemplos Práticos

### Exemplo 1: Operação Perfeita
```
Score: 85/100
Sinal: COMPRA AGRESSIVA (Confiança 92%)
Multi-TF: 1h=COMPRA, 4h=COMPRA, 1d=ALTA
R/R: 1:1.8
Justificativa: 4 confirmações positivas

✓ ENTRAR COM CONFIANÇA
- Entrada: 28,35
- Stop: 27,50
- Alvo 1: 29,50
- Alvo 2: 30,65
```

### Exemplo 2: Operação Questionável
```
Score: 45/100
Sinal: NEUTRO (Confiança 52%)
Multi-TF: 1h=COMPRA, 4h=NEUTRO, 1d=ALTA
R/R: 1:1.2
Justificativa: Indicadores mistos

⚠️ AGUARDAR CONFIRMAÇÃO
- Não entrar ainda
- Esperar score > 60
- Observar próximo candle
```

### Exemplo 3: Operação a Evitar
```
Score: 25/100
Sinal: VENDA (Confiança 65%)
Multi-TF: 1h=VENDA, 4h=NEUTRO, 1d=COMPRA
R/R: 1:0.9
Justificativa: Sinais conflitantes

❌ EVITAR OPERAÇÃO
- Timeframes divergem
- Score muito baixo
- Retorno desfavorável
```

---

## 💡 Dicas Profissionais

### 1. Use Análise Multi-Timeframe
- Se todos os 3 TF concordam, força = 100%
- Se 2 concordam, força = 70%
- Se divergem, força = 30%

### 2. Respeite o Score Operacional
- Score > 70 = pode operar
- Score 50-70 = validar melhor
- Score < 50 = evitar

### 3. Acompanhe Risco/Retorno
- Nunca faça R/R < 1
- Preferir R/R > 1.5
- Ideal: R/R > 2

### 4. Leia a Justificativa
- Não confie apenas na cor
- Entenda o raciocínio da IA
- Valide com sua análise

### 5. Confirme com Candle Anterior
- Espere fechar de candle
- Não entre no meio da vela
- Risco menor ao confirmar

### 6. Use Backtest para Validar
- Execute antes de operar
- Se taxa de acerto < 50%, cuidado
- Se retorno < 5%, rever estratégia

---

## 🔧 Ajustes Avançados

### Variar Timeframe
- **Scalping**: 1h
- **Day Trade**: 1h + 4h
- **Swing Trade**: 4h + 1d
- **Posição**: 1d

### Entradas Agressivas
- Esperar Score > 75
- Confiança > 80%
- Todos os TF concordam

### Entradas Conservadoras
- Score > 60 suficiente
- Confiança > 60%
- Pelo menos 2 TF concordam

### Stop Loss Tighter
- Usar (Stop - ATR×0.5) para mais aperto
- Protege mais lucro
- Risco de sair cedo

---

## ⚙️ Troubleshooting

### Gráfico não carrega
```
1. Refresh F5
2. Verificar conexão internet
3. Aguardar 5 segundos
4. Trocar ativo
```

### Dados estranhos
```
- Dados são históricos/simulados
- Para reais, conectar API corretora
```

### Lentidão
```
- Fechar abas desnecessárias
- Limpar cache (Ctrl+Shift+Del)
- Atualizar página
```

---

## 📞 Suporte

Para mais informações:
1. Leia ADVANCED_README.md
2. Consulte código em ia/analysis.py
3. Teste com test_system.py

---

**Bom trading! 📈**
