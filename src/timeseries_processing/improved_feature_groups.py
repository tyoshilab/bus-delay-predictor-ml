# ========================================
# Trip-based 特徴量グループ（推奨）
# ========================================
# 用途: 個別バス（trip_id）単位のシーケンス作成
# 特徴: prev_stop_delay（相関0.84）を活用可能
# 期待R²: 0.65-0.75, MAE: 70-85秒
feature_groups_trip_based = {
    'temporal': [
        # 周期エンコーディング
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
        # ラッシュアワー（One-hot表現）
        'rush_hour_morning',   # 朝ラッシュ（7-9時）
        'rush_hour_evening',   # 夕ラッシュ（17-19時）
        # 時間帯カテゴリ（One-hot表現）
        'time_late_night',     # 深夜（0-4時）
        'time_early_morning',  # 早朝（5-6時）
        'time_morning',        # 朝（7-11時）
        'time_daytime',        # 日中（12-16時）
        'time_evening',        # 夕方（17-20時）
        'time_night',          # 夜（21-23時）
        # 学校通学時間帯
        'school_commute_hour',
        # 週末・祝日
        'is_weekend', 'is_holiday',
        # 月内の日（給料日効果）
        'day_of_month'
    ],
    'delay_patterns': [
        # 🚀 上流停留所遅延（Trip-basedでのみ有効）
        'prev_stop_delay',           # 相関0.84 - 最重要！
        'prev_2_stop_delay',         # 相関0.79
        # ルート遅延トレンド（データリーク回避版）
        'route_delay_trend_60min',
        'route_hourly_delay_7d_avg',
        'route_delay_volatility_3h',
        # ⚠️ arrival_delay は入力には含めない（targetのみ）
        'arrival_delay'
    ],
    'region': [
        # 地理情報
        'distance_from_downtown_km',
        'area_density_score',
        'stop_sequence',
        # 方向
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
    'alert': [
        # 🚀 Phase 4: アラート特徴量（期待R² +0.08~0.10）
        # 基本情報
        'has_active_alert',           # アラート有無（0/1）
        'high_impact_alert_count',        # 高影響アラート数（NO_SERVICE, DETOUR）
        # 原因別（バンクーバー特有）
        'alert_police_activity',          # 警察活動（23%）
        'alert_construction',             # 工事
        'alert_technical_problem',        # 技術的問題
        # 影響別（遅延に直結）
        'alert_effect_no_service',        # サービス停止
        'alert_effect_detour',            # 迂回
        # 重症度スコア
        'alert_severity_score'            # 影響度重み付けスコア
    ],
    'target': ['arrival_delay']
}

# ========================================
# Route-based 特徴量グループ
# ========================================
# 用途: ルート・方向（route_id + direction_id）単位のシーケンス作成
# 特徴: 長い時系列（8時間）、ルート全体の傾向を学習
# 注意: prev_stop_delayは使用不可（異なるバスが混在するため）
# 期待R²: 0.50-0.60, MAE: 95-110秒
# trip_based特徴量グループから再利用して作成
feature_groups_route_based = {
    'temporal': feature_groups_trip_based['temporal'].copy(),  # 時間特徴は同じ
    'delay_patterns': [
        # ❌ prev_stop_delay, prev_2_stop_delay は除外
        #    理由: 異なるバス（trip_id）が混在するため機能しない

        # ✅ ルート全体の遅延トレンド（Route-basedで有効）
        'route_delay_trend_60min',
        'route_hourly_delay_7d_avg',
        'route_delay_volatility_3h',

        # ✅ データリーク回避版の統計特徴（tmp.sqlから）
        'delay_mean_by_route_hour',          # 過去7日間の同ルート・同時刻平均
        'delay_mean_by_trip_headsign_hour',  # 過去7日間の同行先・同時刻平均

        # 時系列入力として使用
        'arrival_delay'
    ],
    'region': feature_groups_trip_based['region'].copy(),  # 地理特徴は同じ
    'weather': feature_groups_trip_based['weather'].copy(),  # 天候特徴は同じ
    'alert': feature_groups_trip_based['alert'].copy(),      # アラート特徴は同じ
    'target': ['arrival_delay']
}

# ========================================
# デフォルト特徴量グループ（後方互換性）
# ========================================
# Trip-basedをデフォルトとして推奨
feature_groups = feature_groups_trip_based


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
