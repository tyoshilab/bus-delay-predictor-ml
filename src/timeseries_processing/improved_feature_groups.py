# ========================================
# 特徴量グループ
# ========================================
feature_groups = {
    'temporal': [
        # 周期エンコーディング
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
        # ラッシュアワー（0/1/2の3値）
        'rush_hour_type',
        # 学校通学時間帯（新規）
        'school_commute_hour',
        # 週末・祝日
        'is_weekend', 'is_holiday',
        # 月内の日（給料日効果）
        'day_of_month'
    ],
    'delay_patterns': [
        # 🚀 上流停留所遅延（最重要）
        'prev_stop_delay',
        'prev_2_stop_delay',
        # ルート遅延トレンド（データリーク回避版）
        'route_delay_trend_60min',
        'route_hourly_delay_7d_avg',
        'route_delay_volatility_3h',
        # 目的変数も含める（ConvLSTMの入力として）
        'arrival_delay'
    ],
    'region': [
        # 地理情報
        'distance_from_downtown_km',
        'area_density_score',
        'stop_sequence',
        # 方向（既存）
        'direction_id'
    ],
    'weather': [
        # 基本気象
        'humidex',
        'wind_speed',
        'weather_rainy',
        # 🚀 新規: 季節性除去した偏差
        'humidex_deviation_7d',
        # 🚀 新規: 変化率
        'wind_speed_change_1h'
    ],
    'target': ['arrival_delay']
}

# ========================================
# ベースライン特徴量グループ（現行）
# ========================================
feature_groups_baseline = {
    'temporal': [
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
        'is_peak_hour', 'is_weekend', 'arrival_delay'
    ],
    'region': [
        'direction_id', 'stop_sequence',
        'delay_mean_by_route_hour', 'distance_from_downtown_km',
        'area_density_score'
    ],
    'weather': ['humidex', 'wind_speed', 'weather_rainy'],
    'target': ['arrival_delay']
}
