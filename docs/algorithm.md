# 算法规格 — 10 层信号系统

> 所有规则均经缠论 108 课原文逐层校验。修正处标注 `[修正]`。

---

## L0: K 线包含关系处理

**原文出处**：第 062 课、第 065 课

**模块**：`chanquant/core/kline.py` — `KLineProcessor`

### 规则

```
0.1 包含判定:
  K[i].high >= K[i+1].high AND K[i].low <= K[i+1].low → K[i] 包含 K[i+1]
  K[i+1].high >= K[i].high AND K[i+1].low >= K[i].low → K[i+1] 包含 K[i]

0.2 合并方向:
  取前一根非包含 K 线判断方向
  K[i].high > K[i-1].high → UP
  K[i].low < K[i-1].low  → DOWN

0.3 合并处理:
  UP:   merged.high = max(highs), merged.low = max(lows)
  DOWN: merged.high = min(highs), merged.low = min(lows)

0.4 递归:
  合并后新 K 线继续与下一根比较
```

### API

```python
proc = KLineProcessor()
std_kline: StandardKLine | None = proc.feed(raw_kline)
last = proc.flush()  # 获取最后一根缓冲的 K 线
```

---

## L1: 分型识别

**原文出处**：第 062 课、第 077 课

**模块**：`chanquant/core/fractal.py` — `FractalDetector`

### 规则

```
1.1 顶分型: K[i].high > K[i-1].high AND K[i].high > K[i+1].high
1.2 底分型: K[i].low  < K[i-1].low  AND K[i].low  < K[i+1].low
1.3 交替处理:
    连续同类 → 顶保留高者，底保留低者
    最终序列: 底-顶-底-顶-底...
```

### 数据结构

```python
@dataclass(frozen=True)
class Fractal:
    type: FractalType        # TOP / BOTTOM
    timestamp: datetime
    extreme_value: Decimal   # 极值
    kline_index: int         # K 线索引
    elements: tuple[StandardKLine, StandardKLine, StandardKLine]
```

---

## L2: 笔的划分

**原文出处**：第 062 课、第 077 课

**模块**：`chanquant/core/stroke.py` — `StrokeBuilder`

### 规则

```
2.1 构成条件:
    - 顶底分型交替
    - 分型之间 ≥ 5 根标准化 K 线（index 差 ≥ 4）
    - 向上笔: 底.extreme < 顶.extreme
    - 向下笔: 顶.extreme > 底.extreme

2.2 属性扩展:
    对每笔计算 MACD 柱面积（为 L6 准备）
    macd_area = Σ|MACD_histogram[i]| for i in stroke_range
```

---

## L3: 线段划分 [含关键修正]

**原文出处**：第 067 课、第 077 课

**模块**：`chanquant/core/segment.py` — `SegmentBuilder`

### 规则

```
3.0 构成条件: 至少 3 笔，前三笔有重叠

3.1 特征序列构建:
    向上线段 → 取所有向下笔为特征序列
    向下线段 → 取所有向上笔为特征序列

3.2 特征序列标准化:
    对特征序列做包含关系处理

3.3 第一种情况 (无缺口):
    标准特征序列出现分型 + 第一/第二元素间无缺口
    → 线段在分型极值处结束

3.4 第二种情况 [修正]:
    标准特征序列出现分型 + 第一/第二元素间存在缺口
    → 从该分型极值开始构建反向特征序列
    → 反向序列出现分型 → 线段结束
    → 反向序列无分型 → 线段继续延伸

3.5 缺口判定:
    向上线段: Xi.low > Xi+1.high → 缺口
    向下线段: Si.high < Si+1.low → 缺口

3.6 方向判定 [修正]:
    线段方向由实际价格走势决定:
      first_price = 第一笔起点价格
      last_price  = 最后一笔终点价格
      last > first → UP, 否则 → DOWN
    而非由特征序列终结方向决定。
    原因: 特征序列终结方向可能与实际价格走势相反。

3.7 双向检测 [修正]:
    SegmentBuilder 同时检查当前方向和反方向的特征序列终结。
    原因: 初始方向可能与实际线段方向不匹配。
```

> **修正说明**：多数开源实现仅有第一种情况，遗漏第二种导致趋势行情中线段被提前终结。

---

## L4: 中枢识别

**原文出处**：第 018 课、第 020 课

**模块**：`chanquant/core/center.py` — `CenterDetector`

### 规则

```
4.1 形成: 三段连续走势的重叠区间
    ZG = min(seg1.high, seg2.high)  # 中枢上沿
    ZD = max(seg1.low, seg2.low)    # 中枢下沿
    GG = max(所有 high)             # 波动最高
    DD = min(所有 low)              # 波动最低
    ZG > ZD → 中枢成立

4.2 延伸: 新段与 [ZD, ZG] 有重叠 → 更新 GG/DD，ZG/ZD 不变
4.3 新生: 新段完全离开 [ZD, ZG] → 当前中枢完成，新段开始下一个缓冲
4.4 扩展: [已移除] 原实现会合并 [DD,GG] 重叠的中枢，导致独立中枢被错误合并。
         现在保持各中枢独立，不做自动合并。
```

---

## L5: 趋势与盘整分类

**原文出处**：第 017 课、第 018 课

**模块**：`chanquant/core/trend.py` — `TrendClassifier`

### 规则

```
5.1 盘整: 仅一个中枢 → CONSOLIDATION
5.2 上升趋势: ≥ 2 中枢，后 ZD > 前 ZG（不重叠向上）→ UP_TREND
5.3 下降趋势: ≥ 2 中枢，后 ZG < 前 ZD（不重叠向下）→ DOWN_TREND

实现细节 [修正]:
  - 使用滑动窗口（最近 2-3 个中枢）判定趋势，而非要求所有中枢都同向
  - 先检查最近 3 个，再 fallback 检查最近 2 个
  - 原因：实际市场数据中历史中枢可能有方向变化，全局检查过于严格

标准结构: a + A + b + B + c
  a = 第一中枢前走势（entry segment）
  A = 倒数第二个中枢
  b = 连接段（centers 之间的 segment）
  B = 最后中枢
  c = 最后中枢后走势（exit segment）

连接段查找 [修正]:
  - 严格模式：段完全在两中枢时间区间之间
  - 宽松模式：段跨越中枢边界但主体在区间内（中枢常共享边界段）
```

---

## L6: 背驰判断 [含两处修正]

**原文出处**：第 024 课、第 037 课

**模块**：`chanquant/core/divergence.py` — `DivergenceDetector`

### [修正 1] 比较对象: a 段 vs c 段

原文明确 "C 段的 MACD 柱子面积比 A 段的面积要小"（第 024 课）。A 段指第一中枢前，C 段指最后中枢后。常见错误是比较 b vs c。

### [修正 2] c 段前提条件

"c 至少包含对 B 的一个第三类买卖点"（第 037 课）。不满足则归类为中枢震荡，用盘整背驰处理。

### 规则

```
6.1 趋势背驰:
    前提: a+A+b+B+c 完整趋势 + c 含 B3 + c 创新极值
    判断: c_macd_area < a_macd_area → 背驰
    分界: MACD 黄白线在 B 处回拉 0 轴附近

    [修正] Fallback: 无经典 a+A+b+B+c 结构时（segment_a/segment_c 为 None），
    取最近两个同向段（UP_TREND 取最后两个 UP 段，DOWN_TREND 取最后两个 DOWN 段）
    做 MACD 面积比较。原因：实际数据中经典结构难以精确匹配。

6.2 盘整背驰:
    场景: 仅一个中枢，或 c 不含 B3
    比较: 中枢结束后的离开段中，第一个 vs 最后一个同向段

6.3 多重确认 (至少满足 2/3):
    □ MACD 柱面积缩小 (c_area < a_area)
    □ DIF 值不创新极值 (c_dif < a_dif)
    □ 面积衰竭 (c_area / a_area < 0.8)
    [注意] 条件 1 和 3 高度相关（3 成立则 1 必成立），实质为两条件

6.4 成交量辅助:
    volume_ratio = c 段均量 / a 段均量
    缩量 (<0.7) + MACD 背驰 → 可信度 +20%
    放量 (>1.3) + MACD 背驰 → 可信度 -15%

强度: strength = 1 - c_area / a_area
```

---

## L7: 三类买卖点

**原文出处**：第 020 课、第 053 课

**模块**：`chanquant/core/signal.py` — `SignalGenerator`

### B1/S1 — 趋势背驰转折

```
B1: 下降趋势 + 底背驰 → 转折买入     (第024课)
S1: 上升趋势 + 顶背驰 → 转折卖出
强度: 最高（趋势级别转折）
```

### B2/S2 — 三种触发条件 [修正: 新增条件 2/3]

```
条件 1: B1 后不创新低（不创新高）
条件 2: B1 后盘整背驰               [新增, 第053课]
条件 3: 小转大（无当前级别 B1）       [新增, 第053课]
强度: ★★★★（最适合散户）
```

### B3/S3 — 中枢突破确认

```
B3: 次级别向上离开中枢 → 回试低点 > ZG → 买点  (第020课)
S3: 次级别向下离开中枢 → 回抽高点 < ZD → 卖点
注意: 必须是第一次回试
```

---

## L8: 区间套（多级别联立）

**原文出处**：第 030 课、第 037 课

**模块**：`chanquant/core/nesting.py` — `IntervalNester`

### 规则

```
8.1 递进定位:
    Step 1: 大级别确认背驰段
    Step 2: 次级别定位（在大级别背驰段内寻找买卖点）
    Step 3: 次次级别精确定位
    Step 4: 最小可操作级别 B1 作为实际信号

8.2 大买小原则:
    大级别=卖 AND 小级别=买 → 不操作（一票否决）
    大级别=买 AND 小级别=买 → 强信号
    大级别=买 AND 小级别=卖 → 小级别减仓

8.3 级别映射:
    月线 → 周线 → 日线
    周线 → 日线 → 30分钟
    日线 → 30分钟 → 5分钟
    30分钟 → 5分钟 → 1分钟
```

---

## L9: 评分排序

**模块**：`chanquant/scoring/scorer.py` — `SignalScorer`

工程化设计，非缠论原文。

```
Score = signal_type_score × timeframe_weight × divergence_strength
        × trend_alignment × volume_factor

signal_type_score: B1/S1=5, B2/S2=4, B3/S3=5
timeframe_weight:  月=8, 周=5, 日=3, 30m=2, 5m=1
divergence_strength: 1 - (c_area / a_area), 范围 [0, 1]
trend_alignment: 同向=3, 中性=2, 逆向=1
volume_factor: 0.5 ~ 1.5

过滤条件:
  □ trend_alignment >= 2
  □ divergence_strength >= 0.3
  □ 信号时效 < 3 根 K 线
```

---

## L10: 风控与执行 (实验性 / 仅限回测)

**模块**：`chanquant/execution/position.py`

### ATR 仓位计算

```
position_size = risk_per_trade / (ATR_14 × multiplier)
risk_per_trade = equity × risk_pct

B1: risk_pct = 2%,  分批 50%
B2: risk_pct = 1.5%, 分批 30%
B3: risk_pct = 1%,  分批 20%
```

### 多层止损 (优先级从高到低)

```
1. Portfolio Drawdown: >10% 减半, >15% 清仓
2. Hard Stop: 跌破中枢 DD → 无条件止损
3. Time Stop: 持仓 > 2× 信号周期 → 平仓
4. Trailing Stop: 浮盈 > 1R → 移动止损 = 最高价 - ATR×1.5
```

---

## 修正汇总

| # | 优先级 | 层级 | 修正内容 | 原文依据 |
|---|--------|------|---------|---------|
| 1 | 高 | L3 | 补充第二种情况（缺口 + 反向序列二次确认） | 第 067 课 |
| 2 | 高 | L3 | 线段方向由实际价格走势决定，非特征序列终结方向 | — |
| 3 | 高 | L4 | 移除中枢自动合并（`expand_centers`），保持独立中枢 | 第 017 课 |
| 4 | 高 | L5 | 滑动窗口趋势判定（最近 2-3 个中枢），非要求全部中枢同向 | 第 018 课 |
| 5 | 高 | L6 | 比较对象修正为 a vs c | 第 024/037 课 |
| 6 | 高 | L6 | 无经典 a+A+b+B+c 结构时，fallback 到最近两个同向段比较 | — |
| 7 | 中 | L6 | c 必须含 B 的第三类买卖点 | 第 037 课 |
| 8 | 中 | L7 | B2 补充盘整背驰 + 小转大 | 第 053 课 |
| 9 | 中 | L7 | B3/S3 累积所有有效信号（非仅最后一个） | — |
| 10 | 中 | L7 | 信号按 (type, timestamp) 去重累积，非每轮覆盖 | — |
| 11 | 中 | L8 | 替换加权评分为区间套递进定位 | 第 030 课 |

---

## 已知局限 & 与缠论原文的偏差

以下是当前实现与缠论 108 课原文的已知偏差，按优先级排序：

| # | 优先级 | 层级 | 偏差描述 | 影响 | 缠论原文要求 |
|---|--------|------|---------|------|-------------|
| ~~1~~ | ~~P0~~ | ~~L7~~ | ~~B3/S3 基于笔级别突破~~ | ~~已修复~~ | 已改为段级别突破 + 检查所有中枢 + 每中枢仅首次 |
| ~~2~~ | ~~P1~~ | ~~L2~~ | ~~反方向分型丢弃原始起始分型~~ | ~~已修复~~ | 现保留原始起始分型继续等待 |
| ~~3~~ | ~~P1~~ | ~~L7~~ | ~~B2/S2 未限制首次回调~~ | ~~已修复~~ | 现仅在 B1/S1 后首个反向段回调时产生 |
| 4 | **P2** | L6 | `_count_confirmations` 中 stagnation（面积比 <0.8）与 area divergence（c < a）高度相关 | 三条件实质为两条件，背驰判断偏松 | 面积缩小 + DIF 不创新极值 双重确认 |
| 5 | **P2** | L1 | 分型替换（同类型更极端）返回新分型，但 StrokeBuilder 不知道是"替换"还是"新增" | 边缘情况下笔的端点可能不是最极端分型 | 分型替换应通知下游撤回旧分型 |
| 6 | **P3** | L4 | `expand_centers` 函数仍存在但不再调用 | 无功能影响，死代码 | 可移除 |
| 7 | **P3** | L5 | `_find_segment_between` 用宽松匹配（允许边界重叠） | 可能匹配到不精确的连接段 | 理论上应严格时间区间 |
