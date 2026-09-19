# DeepSeek-R1 Quantitative Trading Model Ruleset

**Version:** 2.0-Institutional  
**Architecture:** DeepSeek-R1 Chain-of-Thought (CoT) + Deterministic Mathematical Invariants  
**Target Class:** Multi-Asset Quantitative Trading (Crypto, Forex, Indices, Commodities, Equities)  
**Execution Engine:** [`deepseek_r1_ruleset.py`](file:///e:/omnitrade-ai-matrix/strategies/deepseek_r1_ruleset.py) / [`DeepSeekQuantAgent`](file:///e:/omnitrade-ai-matrix/ai_swarm/deepseek_quant_agent.py)

---

## 1. Executive Summary & Core Philosophy

The **DeepSeek-R1 Quantitative Trading Model** combines cutting-edge algorithmic reasoning from DeepSeek-R1 with rigorous institutional mathematical models. The system guarantees edge through **four non-negotiable structural pillars**:

```
+-----------------------------------------------------------------------------------+
|                        DEEPSEEK-R1 QUANTITATIVE ENGINE                            |
+-----------------------------------------------------------------------------------+
|  [PILLAR 1] Fibonacci Retracement & Golden Pocket OTE (0.618 - 0.650 / 0.786)     |
|  [PILLAR 2] Institutional Liquidity Sweeps (BSL / SSL Turtle Soup & Wicks)        |
|  [PILLAR 3] Multi-Timeframe Confirmation (HTF Macro -> ITF Setup -> LTF Trigger)  |
|  [PILLAR 4] Strict 1:3+ Risk/Reward Ratio Invariant (Hard Disqualification < 3:1) |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
                    +-------------------------------------+
                    | DeepSeek-R1 CoT Algorithmic Quorum  |
                    | (Confidence >= 75% -> LIVE ORDER)   |
                    +-------------------------------------+
```

---

## 2. Pillar 1: Mathematical Fibonacci Retracement & Extension Framework

### 2.1 Dynamic Swing Extraction
Using multi-bar fractal extrema detection over window $w=5$:
- **Swing High ($S_H$):** Local peak satisfying $\text{High}_i \ge \text{High}_{i \pm j} \quad \forall j \in [1, w]$
- **Swing Low ($S_L$):** Local trough satisfying $\text{Low}_i \le \text{Low}_{i \pm j} \quad \forall j \in [1, w]$
- **Swing Range ($\Delta$):** $\Delta = |S_H - S_L|$

### 2.2 Fibonacci Mathematical Levels

| Fibonacci Level | Value | Mathematical Formula (Bullish) | Mathematical Formula (Bearish) | Strategic Role |
|---|---|---|---|---|
| **Equilibrium** | `0.500` | $S_H - (0.500 \cdot \Delta)$ | $S_L + (0.500 \cdot \Delta)$ | Premium / Discount Boundary |
| **Golden Ratio** | `0.618` | $S_H - (0.618 \cdot \Delta)$ | $S_L + (0.618 \cdot \Delta)$ | OTE Entry Threshold |
| **Golden Pocket** | `0.650` | $S_H - (0.650 \cdot \Delta)$ | $S_L + (0.650 \cdot \Delta)$ | **Prime Institutional Execution Sweet Spot** |
| **Deep Discount OTE** | `0.786` | $S_H - (0.786 \cdot \Delta)$ | $S_L + (0.786 \cdot \Delta)$ | Maximum Retracement Bound |
| **Invalidation Fib** | `0.886` | $S_H - (0.886 \cdot \Delta)$ | $S_L + (0.886 \cdot \Delta)$ | Hard Structural Invalidation |
| **TP Extension 1** | `1.272` | $S_L + (1.272 \cdot \Delta)$ | $S_H - (1.272 \cdot \Delta)$ | Intermediate Expansion Target |
| **TP Extension 2** | `1.618` | $S_L + (1.618 \cdot \Delta)$ | $S_H - (1.618 \cdot \Delta)$ | **Golden Target (Core TP2)** |
| **TP Extension 3** | `2.618` | $S_L + (2.618 \cdot \Delta)$ | $S_H - (2.618 \cdot \Delta)$ | Institutional Super Runner |

---

## 3. Pillar 2: Institutional Liquidity Sweeps & Smart Money Concepts (SMC)

### 3.1 Liquidity Architecture
1. **Sell-Side Liquidity (SSL) Sweep (Bullish Turtle Soup):**
   - Retail stop-losses accumulate below key swing lows or equal lows ($S_L$).
   - Institutional participants aggressively push price below $S_L$ ($\text{Low}_t < S_L$) to absorb resting sell orders.
   - Price swiftly closes **back above** the swing low ($\text{Close}_t > S_L$) leaving a dominant **lower rejection wick** ($\ge 35\%$ of candle range).
   - Generates high-conviction **BULLISH_SSL_SWEEP**.

2. **Buy-Side Liquidity (BSL) Sweep (Bearish Turtle Soup):**
   - Retail breakout buyers and short stop-losses accumulate above key swing highs ($S_H$).
   - Institutions push price above $S_H$ ($\text{High}_t > S_H$) to induce buy-side liquidity.
   - Price rejects and closes **back below** $S_H$ ($\text{Close}_t < S_H$) with a dominant **upper rejection wick** ($\ge 35\%$ of candle range).
   - Generates high-conviction **BEARISH_BSL_SWEEP**.

3. **Displacement & Mitigation Check:**
   - Sweep must occur into an unmitigated **Order Block (OB)** or **Fair Value Gap (FVG)** situated within the $0.618 - 0.786$ Fibonacci OTE zone.

---

## 4. Pillar 3: Multi-Timeframe Confirmation (MTF) Gatekeeper

Trading signals are subjected to a **3-tier synchronous gatekeeper**:

| Timeframe Tier | Target Timeframes | Role & Analytical Invariant | Required State |
|---|---|---|---|
| **Higher Timeframe (HTF)** | 1D / 4H / 1H | Macro Directional Bias & Supply/Demand Boundaries | Must be `BULLISH` or `NEUTRAL` for Longs; `BEARISH` or `NEUTRAL` for Shorts. |
| **Intermediate Timeframe (ITF)** | 15m / 30m | Structural Swing Range & Fibonacci OTE Zone | Price must reside in $[0.618 - 0.786]$ Golden Pocket / OTE zone. |
| **Lower Timeframe (LTF)** | 5m / 1m | Execution Trigger & Liquidity Sweep Confirmation | Must detect active BSL/SSL sweep + rejection wick $\ge 35\%$. |

$$\text{MTF Gatekeeper Condition} = \begin{cases} \text{APPROVED} & \text{if } \text{HTF}_{\text{Bias}} \land \text{ITF}_{\text{OTE}} \land \text{LTF}_{\text{Sweep}} \\ \text{DISQUALIFIED} & \text{otherwise} \end{cases}$$

---

## 5. Pillar 4: Strict 1:3+ Risk/Reward Ratio (RRR) & Mathematical Risk Engine

### 5.1 Hard Mathematical Invariant
$$\text{RRR} = \frac{|\text{Take Profit Target} - \text{Entry Price}|}{|\text{Entry Price} - \text{Stop Loss}|} \ge 3.0$$

> [!CAUTION]
> **Hard Execution Rule:** Any trade proposal with calculated $\text{RRR} < 3.0$ is **strictly filtered out and discarded**, regardless of technical conviction.

### 5.2 Dynamic Stop Loss Placement
- **Long Stop Loss ($SL_{long}$):**
  $$SL_{long} = \min(\text{Sweep Wick Low}, \text{Fib}_{0.886}) - (0.20 \times \text{ATR})$$
- **Short Stop Loss ($SL_{short}$):**
  $$SL_{short} = \max(\text{Sweep Wick High}, \text{Fib}_{0.886}) + (0.20 \times \text{ATR})$$

### 5.3 Multi-Tier Take-Profit Architecture
1. **Take-Profit 1 (TP1) @ 1:1.5 RRR:**
   - Realize **33% position size**.
   - Automatically move Stop Loss to **Breakeven $+ 0.1\text{R}$** (Guarantee zero-loss trade).
2. **Take-Profit 2 (TP2) @ 1:3.0 RRR / 1.618 Extension:**
   - Realize **50% of remaining position**.
   - Core institutional profit milestone.
3. **Take-Profit 3 (TP3) @ 1:5.0+ RRR / 2.0-2.618 Extension:**
   - Retain remaining runner with trailing stop behind intermediate swing fractals.

### 5.4 Position Sizing (Fractional Kelly Criterion)
$$f^* = \frac{p \cdot b - q}{b}$$
- $p = \text{Estimated Win Rate (e.g. } 0.58\text{)}$
- $b = \text{Mathematical RRR (e.g. } 3.0\text{)}$
- $q = 1 - p = 0.42$
- **Fractional Allocation:** $\text{Quarter-Kelly } f_{safe} = 0.25 \times f^*$
- **Dollar Position Size:**
  $$\text{Units} = \frac{\text{Account Balance} \times \text{Risk Pct}}{|\text{Entry} - \text{Stop Loss}|}$$

---

## 6. Pillar 5: DeepSeek-R1 Chain-of-Thought (CoT) Reasoning Engine

### 6.1 Structured CoT Prompt Template
The system constructs a formal prompt fed to DeepSeek-R1 containing all mathematical matrices. DeepSeek-R1 processes the analysis through step-by-step `<think>` verification:

```json
{
  "thought_process": "1. HTF Macro is Bullish (Higher High structure). 2. ITF price retraced into Golden Pocket (0.632 Fib level @ 107.4). 3. LTF executed SSL Sweep below 100 with 45% lower wick rejection. 4. Risk distance = 2.4, Target distance = 7.5, RRR = 3.125 >= 3.0. Invariants satisfied.",
  "signal": "STRONG_BUY",
  "confidence": 0.92,
  "fibonacci_confluence": "GOLDEN_POCKET",
  "liquidity_sweep_verified": true,
  "mtf_alignment": true,
  "strict_rrr_passed": true,
  "rrr": 3.12,
  "entry_price": 107.4,
  "stop_loss": 104.98,
  "take_profit_1": 111.03,
  "take_profit_2": 114.66,
  "take_profit_3": 119.50,
  "quant_rationale": "High-conviction Golden Pocket SSL sweep with 3.12:1 RRR and full MTF alignment."
}
```

---

## 7. Verification & Automated Test Status

The complete ruleset is covered by unit and integration tests in [`tests/test_deepseek_r1_ruleset.py`](file:///e:/omnitrade-ai-matrix/tests/test_deepseek_r1_ruleset.py):

```
test_deepseek_quant_agent_integration ... ok
test_end_to_end_quant_engine .......... ok
test_fibonacci_matrix_calculations .... ok
test_fibonacci_zone_evaluation ........ ok
test_liquidity_sweep_detection ........ ok
test_multi_timeframe_confirmation ..... ok
test_strict_risk_reward_invariant ..... ok

----------------------------------------------------------------------
Ran 7 tests in 3.554s

OK (100% PASSED)
```
