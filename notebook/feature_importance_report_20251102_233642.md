
# 特徴量重要度分析レポート

**分析日時**: 2025-11-02 23:36:42  
**モデル**: Bidirectional ConvLSTM best_delay_model_20251102_032300.h5  
**データセット**: delay_analysis_route_based.csv  
**手法**: Permutation Importance (n_repeats=10)  
**評価指標**: MAE (Mean Absolute Error)

---

## 1. 基本情報

- **総特徴量数**: 31
- **分析サンプル数**: 5000
- **ベースラインMAE**: 111.3020 秒 (1.86 分)
- **ベースラインRMSE**: 245.6470 秒 (4.09 分)
- **ベースラインR²**: 0.3859

---

## 2. 特徴量ランキング

| Rank | Feature | Category | Importance | Std |
|------|---------|----------|------------|----- |
| 10 | route_delay_trend_60min | delay_patterns | 2.044417 | 0.150114 |
| 14 | delay_mean_by_trip_headsign_hour | delay_patterns | 0.402477 | 0.042245 |
| 2 | hour_cos | temporal | 0.341090 | 0.125868 |
| 13 | delay_mean_by_route_hour | delay_patterns | 0.303074 | 0.082731 |
| 9 | day_of_month | temporal | 0.197425 | 0.081877 |
| 11 | route_hourly_delay_7d_avg | delay_patterns | 0.165986 | 0.070648 |
| 20 | wind_speed | weather | 0.100263 | 0.082415 |
| 3 | day_sin | temporal | 0.099459 | 0.079092 |
| 5 | rush_hour_type | temporal | 0.041864 | 0.061278 |
| 4 | day_cos | temporal | 0.033509 | 0.037247 |
| 6 | school_commute_hour | temporal | 0.022154 | 0.050858 |
| 23 | wind_speed_change_1h | weather | 0.014540 | 0.038081 |
| 28 | alert_technical_problem | alert | 0.001284 | 0.008906 |
| 27 | alert_construction | alert | 0.000000 | 0.000000 |
| 8 | is_holiday | temporal | 0.000000 | 0.000000 |
| 18 | direction_id | region | -0.001354 | 0.032229 |
| 31 | alert_severity_score | alert | -0.013160 | 0.010279 |
| 16 | area_density_score | region | -0.020675 | 0.030567 |
| 30 | alert_effect_detour | alert | -0.030957 | 0.007207 |
| 29 | alert_effect_no_service | alert | -0.038728 | 0.005039 |
| 21 | weather_rainy | weather | -0.040086 | 0.035402 |
| 17 | stop_sequence | region | -0.061821 | 0.084184 |
| 24 | has_active_alert | alert | -0.063232 | 0.024961 |
| 26 | alert_police_activity | alert | -0.066488 | 0.012646 |
| 12 | route_delay_volatility_3h | delay_patterns | -0.077854 | 0.072625 |
| 25 | high_impact_alert_count | alert | -0.086360 | 0.015933 |
| 19 | humidex | weather | -0.088634 | 0.054247 |
| 15 | distance_from_downtown_km | region | -0.136183 | 0.047939 |
| 1 | hour_sin | temporal | -0.137837 | 0.044212 |
| 7 | is_weekend | temporal | -0.306102 | 0.035265 |
| 22 | humidex_deviation_7d | weather | -0.340830 | 0.047043 |


---

## 3. カテゴリ別分析

| Category | Total Importance | Avg Importance | N Features |
|----------|------------------|----------------|------------|
| Delay_patterns | 2.838100 | 0.567600 | 5 |
| Temporal | 0.291600 | 0.032400 | 9 |
| Region | -0.220000 | -0.055000 | 4 |
| Alert | -0.297600 | -0.037200 | 8 |
| Weather | -0.354700 | -0.070900 | 5 |


---

## 4. 主要な発見

### 4.1 カテゴリ別の重要度ランキング

1. **Delay_patterns**: 合計重要度 2.8381
2. **Temporal**: 合計重要度 0.2916
3. **Region**: 合計重要度 -0.2200

### 4.2 最も重要な単一特徴量

**route_delay_trend_60min** (delay_patternsカテゴリ)
- 重要度: 2.044417
- この特徴量をシャッフルするとMAEが約 2.04秒増加

