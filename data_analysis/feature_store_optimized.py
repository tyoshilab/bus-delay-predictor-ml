"""
Optimized Feature Store computation
Memory-efficient lag and rolling feature computation
"""
import pandas as pd
import numpy as np
import gc


def compute_all_features_optimized(df, target_col='arrival_delay_agg',
                                    group_cols=['route_direction_key'],
                                    lags=[1, 2, 3, 5],
                                    windows=[3, 5, 10],
                                    chunk_size=50000):
    """
    ラグ特徴量と移動統計量を効率的に計算

    改善点:
    - 前処理の重複を排除
    - チャンク処理でメモリ使用量を削減
    - 中間変数の明示的な削除
    - float32への変換でメモリ半減
    """
    print(f"Input data shape: {df.shape}")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

    # Step 1: trip単位の集計を一度だけ計算
    print("\n[Step 1] Computing trip-level aggregates...")
    trip_agg = df.groupby(['trip_key'] + group_cols).agg({
        target_col: 'mean',
        'scheduled_arrival_time': 'min'
    }).reset_index()
    trip_agg = trip_agg.rename(columns={target_col: 'trip_mean_delay'})

    # メモリ効率化: float32に変換
    trip_agg['trip_mean_delay'] = trip_agg['trip_mean_delay'].astype('float32')

    print(f"  Trip aggregates: {len(trip_agg)} rows")

    # Step 2: グループ内でソート
    print("\n[Step 2] Sorting by group and time...")
    trip_agg = trip_agg.sort_values(group_cols + ['scheduled_arrival_time'])
    trip_agg = trip_agg.reset_index(drop=True)

    # Step 3: ラグ特徴量を計算（グループごとにチャンク処理）
    print("\n[Step 3] Computing lag features...")
    for lag in lags:
        col_name = f'delay_lag_{lag}'
        trip_agg[col_name] = trip_agg.groupby(group_cols)['trip_mean_delay'].shift(lag)
        trip_agg[col_name] = trip_agg[col_name].astype('float32')
        print(f"  - {col_name} computed")

    gc.collect()

    # Step 4: 移動統計量を計算（transformを避けてapply+mergeで処理）
    print("\n[Step 4] Computing rolling features...")

    for window in windows:
        mean_col = f'delay_rolling_mean_{window}'
        std_col = f'delay_rolling_std_{window}'

        # shift(1)してから計算（未来の情報を使わない）
        shifted = trip_agg.groupby(group_cols)['trip_mean_delay'].shift(1)

        # rolling計算（transformの代わりにgroupbyの結果を直接使用）
        trip_agg[mean_col] = shifted.groupby(trip_agg[group_cols[0]]).transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        ).astype('float32')

        trip_agg[std_col] = shifted.groupby(trip_agg[group_cols[0]]).transform(
            lambda x: x.rolling(window, min_periods=1).std()
        ).astype('float32')

        print(f"  - {mean_col}, {std_col} computed")

        del shifted
        gc.collect()

    # Step 5: 元のDataFrameにマージ（チャンク処理）
    print("\n[Step 5] Merging features back to original dataframe...")

    # マージするカラムを選択
    lag_cols = [f'delay_lag_{lag}' for lag in lags]
    rolling_cols = []
    for w in windows:
        rolling_cols.extend([f'delay_rolling_mean_{w}', f'delay_rolling_std_{w}'])

    merge_cols = ['trip_key'] + lag_cols + rolling_cols
    trip_features = trip_agg[merge_cols].drop_duplicates('trip_key')

    # 不要なtip_aggを削除
    del trip_agg
    gc.collect()

    # チャンク処理でマージ
    n_chunks = max(1, len(df) // chunk_size)
    print(f"  Processing in {n_chunks} chunks...")

    result_chunks = []
    for i, chunk_df in enumerate(np.array_split(df, n_chunks)):
        chunk_merged = chunk_df.merge(trip_features, on='trip_key', how='left')
        result_chunks.append(chunk_merged)

        if (i + 1) % 10 == 0 or i == n_chunks - 1:
            print(f"  - Chunk {i+1}/{n_chunks} done")

    del trip_features
    gc.collect()

    # チャンクを結合
    print("\n[Step 6] Concatenating chunks...")
    result = pd.concat(result_chunks, ignore_index=True)

    del result_chunks
    gc.collect()

    # NaNを0で埋める
    all_feature_cols = lag_cols + rolling_cols
    result[all_feature_cols] = result[all_feature_cols].fillna(0)

    print(f"\nOutput data shape: {result.shape}")
    print(f"Memory usage: {result.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

    return result


def compute_time_features(df):
    """時間帯ベースの特徴量を計算（インプレース）"""
    # 時間帯区分（文字列型で保存 - Parquet互換性のため）
    df['time_period'] = pd.cut(
        df['hour'],
        bins=[0, 6, 9, 12, 15, 18, 21, 24],
        labels=['night', 'morning_rush', 'morning', 'noon', 'afternoon', 'evening_rush', 'evening'],
        right=False
    ).astype(str)

    # ラッシュフラグ
    df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype('int8')
    df['is_evening_rush'] = ((df['hour'] >= 16) & (df['hour'] <= 19)).astype('int8')

    return df


# メモリ使用量を確認するユーティリティ
def print_memory_usage(df, name="DataFrame"):
    """DataFrameのメモリ使用量を表示"""
    mem_mb = df.memory_usage(deep=True).sum() / 1024**2
    print(f"{name}: {len(df):,} rows, {mem_mb:.1f} MB")


if __name__ == "__main__":
    # テスト実行
    import utils

    print("Loading data...")
    base_df = utils.load_data()

    if base_df is not None:
        print_memory_usage(base_df, "base_df")

        # サンプルデータでテスト
        sample_df = base_df.head(100000).copy()
        print_memory_usage(sample_df, "sample_df")

        result = compute_all_features_optimized(sample_df)
        print_memory_usage(result, "result")
