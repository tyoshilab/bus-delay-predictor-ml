
# 特徴量重要度分析レポート（Trip-based）

**分析日時**: 2025-11-03 00:36:54  
**アプローチ**: Trip-based (individual trip sequences)  
**モデル**: Bidirectional ConvLSTM best_delay_model_trip_based_20251102_061332.h5  
**データセット**: delay_analysis_trip_based.csv  
**手法**: Permutation Importance (n_repeats=10, cross_sample strategy)  
**評価指標**: MAE (Mean Absolute Error)

---

## 1. 基本情報

- **総特徴量数**: 31
- **分析サンプル数**: 5000
- **訓練トリップ数**: 3,155
- **テストトリップ数**: 351
- **ベースラインMAE**: 175.9200 秒 (2.93 分)
- **ベースラインRMSE**: 236.6304 秒 (3.94 分)
- **ベースラインR²**: 0.5712

---

## 2. 特徴量ランキング（Top 20）

| Rank | Feature | Category | Importance | Std |
|------|---------|----------|------------|----- |
| 1 | prev_stop_delay | delay_patterns | 31.324343 | 0.377220 |
| 2 | prev_2_stop_delay | delay_patterns | 19.436973 | 0.377453 |
| 3 | route_hourly_delay_7d_avg | delay_patterns | 5.117359 | 0.374258 |
| 4 | hour_sin | temporal | 4.075590 | 0.314728 |
| 5 | humidex | weather | 2.223550 | 0.226646 |
| 6 | route_delay_volatility_3h | delay_patterns | 1.815405 | 0.255784 |
| 7 | weather_rainy | weather | 1.801601 | 0.199661 |
| 8 | has_active_alert | alert | 1.371155 | 0.294599 |
| 9 | wind_speed | weather | 1.265082 | 0.179810 |
| 10 | day_of_month | temporal | 1.170077 | 0.347948 |
| 11 | day_sin | temporal | 1.087097 | 0.233404 |
| 12 | route_delay_trend_60min | delay_patterns | 0.967438 | 0.252298 |
| 13 | humidex_deviation_7d | weather | 0.898581 | 0.118352 |
| 14 | is_weekend | temporal | 0.848190 | 0.288742 |
| 15 | day_cos | temporal | 0.536303 | 0.270882 |
| 16 | area_density_score | region | 0.423053 | 0.195714 |
| 17 | hour_cos | temporal | 0.266948 | 0.147209 |
| 18 | alert_severity_score | alert | 0.264764 | 0.061062 |
| 19 | alert_technical_problem | alert | 0.259412 | 0.059087 |
| 20 | distance_from_downtown_km | region | 0.236762 | 0.072788 |


---

## 3. カテゴリ別分析

| Category | Total Importance | Avg Importance | N Features |
|----------|------------------|----------------|------------|
| Delay_patterns | 58.661500 | 11.732300 | 5 |
| Temporal | 7.984200 | 0.887100 | 9 |
| Weather | 5.790600 | 1.158100 | 5 |
| Alert | 2.011400 | 0.251400 | 8 |
| Region | 0.608000 | 0.152000 | 4 |


---

## 4. 主要な発見

### 4.1 カテゴリ別の重要度ランキング

1. **Delay_patterns**: 合計重要度 58.6615
2. **Temporal**: 合計重要度 7.9842
3. **Weather**: 合計重要度 5.7906

### 4.2 最も重要な単一特徴量

**prev_stop_delay** (delay_patternsカテゴリ)
- 重要度: 31.324343
- この特徴量をシャッフルするとMAEが約 31.32秒増加

### 4.3 Trip-based特有の知見


**prev_stop_delay**の重要度:
- ランク: 1位
- 重要度: 31.324343
- 全体の41.73%を占める
- 予想通り、上流停留所の遅延情報が予測に重要


---

## 5. Route-based vs Trip-based 比較

| 項目 | Route-based | Trip-based |
|------|-------------|------------|
| グループ化 | route_id + direction_id | trip_id |
| シーケンス | 8時間 | 8停留所 |
| 重要な特徴 | ルート全体の傾向 | 上流停留所遅延 |
| R² Score | ~0.50-0.60 | ~0.57 |
| MAE | - | 2.93 min |

---

**生成日時**: 2025-11-03 00:36:54
