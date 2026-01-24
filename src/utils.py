
import os
from src import const
import json
import glob
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Any
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


@dataclass
class ModelEvaluationResult:
    """統一されたモデル評価結果"""
    model_name: str
    mae: float
    rmse: float
    r2: float
    direction_accuracy: float
    ontime_accuracy: float
    range_accuracies: Dict[str, float]
    delay_level_analysis: Dict[str, Dict[str, float]] = field(default_factory=dict)
    n_samples: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return asdict(self)

    def to_series(self) -> pd.Series:
        """比較用のpd.Seriesに変換"""
        data = {
            'Model': self.model_name,
            'MAE (s)': self.mae,
            'RMSE (s)': self.rmse,
            'R²': self.r2,
            'Direction Acc': self.direction_accuracy,
            'On-Time Acc': self.ontime_accuracy,
            **{f'{k}': v for k, v in self.range_accuracies.items()},
            'N Samples': self.n_samples,
        }
        return pd.Series(data)

    def summary(self) -> str:
        """フォーマットされたサマリーを出力"""
        output = f"""
{'='*60}
Model: {self.model_name}
{'='*60}

--- Overall Metrics ---
MAE:  {self.mae:.2f} seconds
RMSE: {self.rmse:.2f} seconds
R²:   {self.r2:.4f}
Direction Accuracy: {self.direction_accuracy:.2%}
On-Time Accuracy:   {self.ontime_accuracy:.2%}

--- Range Accuracies ---"""
        for range_name, acc in self.range_accuracies.items():
            output += f"\n{range_name}: {acc:.2%}"

        if self.delay_level_analysis:
            output += f"""

--- Delay Level Analysis ---
{'Level':<14} {'Count':<8} {'%':<7} {'MAE':<8} {'RMSE':<8} {'Dir Acc':<8}
{'-'*60}"""
            for level, metrics in self.delay_level_analysis.items():
                output += f"\n{level:<14} {metrics['count']:<8} {metrics['percentage']:<6.1f}% "
                output += f"{metrics['mae']:<7.1f}s {metrics['rmse']:<7.1f}s {metrics['direction_accuracy']:.2%}"

        output += f"""

--- Practical Summary ---
• 1分以内精度: {self.range_accuracies.get('Within 1min', 0):.1%}
• 2分以内精度: {self.range_accuracies.get('Within 2min', 0):.1%}
• 方向予測精度: {self.direction_accuracy:.1%}
• サンプル数: {self.n_samples:,}
"""
        return output


def evaluate_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str,
    config: Optional[Dict[str, Any]] = None,
    include_delay_analysis: bool = True,
) -> ModelEvaluationResult:
    """
    統一されたモデル評価関数

    Parameters
    ----------
    y_true : np.ndarray
        実測値 (N, n_stops) or (N,)
    y_pred : np.ndarray
        予測値 (N, n_stops) or (N,)
    model_name : str
        モデル名
    config : dict, optional
        モデル設定（ハイパーパラメータなど）
    include_delay_analysis : bool
        遅延レベル別分析を含めるか

    Returns
    -------
    ModelEvaluationResult
        統一された評価結果
    """
    # Flatten arrays for overall metrics
    y_true_flat = y_true.flatten()
    y_pred_flat = y_pred.flatten()

    # Remove NaN/Inf values
    valid_mask = np.isfinite(y_true_flat) & np.isfinite(y_pred_flat)
    y_true_clean = y_true_flat[valid_mask]
    y_pred_clean = y_pred_flat[valid_mask]

    # Basic metrics
    mae = mean_absolute_error(y_true_clean, y_pred_clean)
    mse = mean_squared_error(y_true_clean, y_pred_clean)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_true_clean, y_pred_clean)

    # Direction accuracy (early/late)
    true_sign = np.sign(y_true_clean)
    pred_sign = np.sign(y_pred_clean)
    direction_accuracy = np.mean(true_sign == pred_sign)

    # On-time accuracy (±60s)
    threshold = 60
    true_ontime = np.abs(y_true_clean) <= threshold
    pred_ontime = np.abs(y_pred_clean) <= threshold
    ontime_accuracy = np.mean(true_ontime == pred_ontime)

    # Range accuracies
    abs_errors = np.abs(y_true_clean - y_pred_clean)
    ranges = {
        'Within 30s': 30,
        'Within 1min': 60,
        'Within 2min': 120,
        'Within 5min': 300
    }
    range_accuracies = {
        name: float(np.mean(abs_errors <= thresh))
        for name, thresh in ranges.items()
    }

    # Delay level analysis
    delay_level_analysis = {}
    if include_delay_analysis:
        delay_levels = {
            'Very Early': (-np.inf, -120),
            'Early': (-120, -30),
            'On Time': (-30, 30),
            'Minor Delay': (30, 300),
            'Major Delay': (300, np.inf)
        }

        for level_name, (min_delay, max_delay) in delay_levels.items():
            if max_delay == np.inf:
                mask = y_true_clean >= min_delay
            elif min_delay == -np.inf:
                mask = y_true_clean < max_delay
            else:
                mask = (y_true_clean >= min_delay) & (y_true_clean < max_delay)

            count = int(np.sum(mask))
            if count > 0:
                level_true = y_true_clean[mask]
                level_pred = y_pred_clean[mask]
                level_mae = mean_absolute_error(level_true, level_pred)
                level_rmse = np.sqrt(mean_squared_error(level_true, level_pred))
                level_dir_acc = np.mean(np.sign(level_true) == np.sign(level_pred))
            else:
                level_mae = level_rmse = level_dir_acc = 0.0

            delay_level_analysis[level_name] = {
                'count': count,
                'percentage': count / len(y_true_clean) * 100 if len(y_true_clean) > 0 else 0,
                'mae': float(level_mae),
                'rmse': float(level_rmse),
                'direction_accuracy': float(level_dir_acc)
            }

    return ModelEvaluationResult(
        model_name=model_name,
        mae=float(mae),
        rmse=float(rmse),
        r2=float(r2),
        direction_accuracy=float(direction_accuracy),
        ontime_accuracy=float(ontime_accuracy),
        range_accuracies=range_accuracies,
        delay_level_analysis=delay_level_analysis,
        n_samples=len(y_true_clean),
        config=config or {}
    )


def compare_models(results: List[ModelEvaluationResult]) -> pd.DataFrame:
    """
    複数モデルの評価結果を比較テーブルとして出力

    Parameters
    ----------
    results : List[ModelEvaluationResult]
        評価結果のリスト

    Returns
    -------
    pd.DataFrame
        比較テーブル
    """
    rows = [r.to_series() for r in results]
    df = pd.DataFrame(rows)
    df = df.set_index('Model')
    return df


def save_evaluation_results(
    results: List[ModelEvaluationResult],
    filepath: str = const.EVALUATION_RESULTS_PATH
):
    """評価結果をJSONファイルに保存"""
    data = [r.to_dict() for r in results]
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {filepath}")


def load_evaluation_results(filepath: str = const.EVALUATION_RESULTS_PATH) -> List[ModelEvaluationResult]:
    """保存された評価結果を読み込み"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    for d in data:
        results.append(ModelEvaluationResult(**d))
    return results


def load_all_evaluation_results(data_dir: str = const.DATA_DIR) -> pd.DataFrame:
    """
    全モデルの評価結果を読み込み、比較テーブルを作成

    Parameters
    ----------
    data_dir : str
        評価結果JSONファイルが保存されているディレクトリ

    Returns
    -------
    pd.DataFrame
        全モデルの比較テーブル

    Example
    -------
    >>> comparison = load_all_evaluation_results()
    >>> print(comparison)
    """
    import glob

    result_files = glob.glob(os.path.join(data_dir, 'evaluation_results_*.json'))

    if not result_files:
        print(f"No evaluation result files found in {data_dir}")
        return pd.DataFrame()

    all_results = []
    for filepath in result_files:
        try:
            results = load_evaluation_results(filepath)
            all_results.extend(results)
            print(f"Loaded: {filepath} ({len(results)} models)")
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    if not all_results:
        return pd.DataFrame()

    comparison_df = compare_models(all_results)

    # Sort by MAE
    comparison_df = comparison_df.sort_values('MAE (s)')

    print(f"\nTotal: {len(all_results)} models loaded")
    return comparison_df


def load_saved_tensors(split_dir: str = const.SPLITTED_DATA_DIR) -> Optional[dict]:
    """
    Load pre-saved model tensors (X/y arrays) produced in 03.

    Returns None if the directory or expected files are missing.
    """
    if not os.path.isdir(split_dir):
        return None

    meta_files = sorted(glob.glob(os.path.join(split_dir, 'meta_*.json')))
    if not meta_files:
        return None

    meta_path = meta_files[-1]
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception:
        return None

    train_file = metadata.get('train_file')
    test_file = metadata.get('test_file')
    if not train_file or not test_file:
        return None

    train_path = os.path.join(split_dir, train_file)
    test_path = os.path.join(split_dir, test_file)
    if not (os.path.exists(train_path) and os.path.exists(test_path)):
        return None

    with np.load(train_path) as train_npz:
        train_data = {key: train_npz[key] for key in train_npz.files}
    with np.load(test_path) as test_npz:
        test_data = {key: test_npz[key] for key in test_npz.files}

    n_stops = int(train_data['X_delays'].shape[-1]) if 'X_delays' in train_data else None

    return {
        'train': train_data,
        'test': test_data,
        'metadata': metadata,
        'meta_path': meta_path,
        'train_path': train_path,
        'test_path': test_path,
        'n_stops': n_stops
    }


def load_data(type: str = 'base') -> Optional[pd.DataFrame]:
    """Load the base datasets from /workspace/notebook"""
    base_path = const.GTFS_REALTIME_DIR
    # Check if files exist, otherwise try to find them or warn
    base_df = pd.DataFrame()
    for file in os.listdir(base_path):
        if file.endswith('.parquet'):
            file_path = os.path.join(base_path, file)

            if not os.path.exists(file_path):
                print(f"Warning: Data files not found in {base_path}")
                return None

            base_df = pd.concat([base_df, pd.read_parquet(file_path)], ignore_index=True)

    if not base_df.empty:
        base_df['start_date'] = base_df['start_date'].astype(str)
    return base_df


# =============================================================================
# Common Data Loading Functions (Shared across 03~07 notebooks)
# =============================================================================

def load_split_data_with_combined(
    split_data_dir: str = const.PROCESSED_DATA_DIR,
    format: str = 'parquet'
) -> tuple:
    """
    Load train/valid/test splits and return combined df_process.

    This function consolidates the common data loading pattern used in
    notebooks 03~07.

    Parameters
    ----------
    split_data_dir : str
        Directory containing split data files
    format : str
        File format ('parquet' or 'csv')

    Returns
    -------
    tuple : (df_train, df_valid, df_test, df_process, split_info)
        df_process is the concatenation of all three splits
        Returns (None, None, None, None, None) if files not found

    Example
    -------
    >>> df_train, df_valid, df_test, df_process, split_info = load_split_data_with_combined()
    >>> if df_process is not None:
    ...     print(f"Total samples: {len(df_process)}")
    """
    from data_process.split import load_split_data, print_split_info

    train_file = f'{split_data_dir}/train.{format}'

    if not os.path.exists(train_file):
        print(f"Split files not found in {split_data_dir}. Please run 02_process_data.ipynb first.")
        return None, None, None, None, None

    df_train, df_valid, df_test, split_info = load_split_data(split_data_dir, format=format)

    # Ensure start_date is string
    for df in [df_train, df_valid, df_test]:
        if 'start_date' in df.columns:
            df['start_date'] = df['start_date'].astype(str)

    # Create combined dataframe
    df_process = pd.concat([df_train, df_valid, df_test], ignore_index=True)

    print("Loaded fixed split data:")
    print_split_info(split_info)

    return df_train, df_valid, df_test, df_process, split_info


def build_stops_dict(df: pd.DataFrame) -> dict:
    """
    Build stops dictionary from dataframe.

    This function consolidates the common stops_dict building pattern.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing 'route_direction_key' and 'stop_sequence' columns

    Returns
    -------
    dict : {route_direction_key: [sorted stop_sequences]}

    Example
    -------
    >>> stops_dict = build_stops_dict(df_process)
    >>> print(f"Number of route-directions: {len(stops_dict)}")
    """
    stops_dict = {}
    for rd_key in df['route_direction_key'].unique():
        rd_df = df[df['route_direction_key'] == rd_key]
        stops_dict[rd_key] = sorted(rd_df['stop_sequence'].unique())
    return stops_dict


def prepare_model_data(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    df_process: pd.DataFrame,
    n_past_trips: int = 5,
    include_train_sequences: bool = True
) -> dict:
    """
    Prepare sequences for model training and evaluation.

    This function consolidates the common sequence preparation pattern
    used in notebooks 03~05, 07.

    Parameters
    ----------
    df_train : pd.DataFrame
        Training data
    df_test : pd.DataFrame
        Test data
    df_process : pd.DataFrame
        Combined data (for building stops_dict)
    n_past_trips : int
        Number of past trips to use for sequences
    include_train_sequences : bool
        Whether to create training sequences (set False for evaluation-only)

    Returns
    -------
    dict : Dictionary containing:
        - 'X_delays_train', 'X_features_train', 'X_agg_train', 'y_train' (if include_train_sequences)
        - 'X_delays_test', 'X_features_test', 'X_agg_test', 'y_test', 'meta_test'
        - 'stops_dict', 'n_stops'

    Example
    -------
    >>> data = prepare_model_data(df_train, df_test, df_process, n_past_trips=5)
    >>> X_delays_test = data['X_delays_test']
    >>> y_test = data['y_test']
    """
    # Build stops_dict from combined data
    stops_dict = build_stops_dict(df_process)

    result = {
        'stops_dict': stops_dict,
        'n_past_trips': n_past_trips
    }

    # Create test sequences
    print("Creating test sequences...")
    X_delays_test, X_features_test, X_agg_test, y_test, meta_test, _, n_stops = \
        create_trip_based_sequences_multi_route(df_test, n_past_trips, stops_dict=stops_dict)

    result.update({
        'X_delays_test': X_delays_test,
        'X_features_test': X_features_test,
        'X_agg_test': X_agg_test,
        'y_test': y_test,
        'meta_test': meta_test,
        'n_stops': n_stops
    })
    # Align reported n_past_trips with actual tensor shape (may change when lag features are precomputed)
    if X_delays_test.size > 0:
        result['n_past_trips'] = X_delays_test.shape[1]

    # Create train sequences if needed
    if include_train_sequences:
        print("Creating train sequences...")
        X_delays_train, X_features_train, X_agg_train, y_train, _, _, _ = \
            create_trip_based_sequences_multi_route(df_train, result['n_past_trips'], stops_dict=stops_dict)

        result.update({
            'X_delays_train': X_delays_train,
            'X_features_train': X_features_train,
            'X_agg_train': X_agg_train,
            'y_train': y_train
        })

    return result


def display_and_save_results(
    evaluation_results: List['ModelEvaluationResult'],
    output_file: str
) -> pd.DataFrame:
    """
    Display comparison table and save evaluation results.

    This function consolidates the common pattern for displaying and
    saving model evaluation results.

    Parameters
    ----------
    evaluation_results : List[ModelEvaluationResult]
        List of evaluation results
    output_file : str
        Path to save JSON results

    Returns
    -------
    pd.DataFrame : Comparison table (or None if no results)

    Example
    -------
    >>> comparison_df = display_and_save_results(evaluation_results, 'data/evaluation_results_baseline.json')
    """
    if not evaluation_results:
        print("No evaluation results to display.")
        return None

    comparison_df = compare_models(evaluation_results)
    print(comparison_df.round(4).to_string())

    save_evaluation_results(evaluation_results, output_file)

    return comparison_df

def create_trip_based_sequences_multi_route(df, n_past_trips=5, stops_dict=None):
    all_X_delays = []
    all_X_features = []
    all_X_agg = []  # 集約特徴量
    all_y = []
    all_meta = []

    base_feature_cols = [
        'hour_of_day'
        , 'arrival_delay'
        , 'day_of_week'
        , 'time_of_day'
        , 'time_sin'
        , 'time_cos'
        , 'is_weekend'
        , 'is_morning_rush_hour'
        , 'is_evening_rush_hour'
        , 'has_active_alert'
        , 'has_detour'
        , 'has_police_alert'
    ]

    region_feature_cols = sorted(
        col for col in df.columns if col.startswith('region_id_')
    )

    feature_cols = base_feature_cols + region_feature_cols

    lag_columns = [c for c in df.columns if c.startswith('lag_arrival_delay_')]
    lag_columns = sorted(
        lag_columns,
        key=lambda c: int(c.rsplit('_', 1)[-1]) if c.rsplit('_', 1)[-1].isdigit() else float('inf')
    )
    use_lag_features = len(lag_columns) > 0

    effective_n_past = min(n_past_trips, len(lag_columns))
    lag_columns = lag_columns[:effective_n_past]

    # route_direction_keyごとに処理
    rd_keys = sorted(df['route_direction_key'].unique())
    print(f"Processing {len(rd_keys)} route-direction combinations")

    if stops_dict is None:
        stops_dict = {}
        for rd_key in rd_keys:
            rd_df = df[df['route_direction_key'] == rd_key]
            stops_dict[rd_key] = sorted(rd_df['stop_sequence'].unique())

    # 全route-directionで共通のstops数を使用（パディング用）
    max_stops = max(len(stops) for stops in stops_dict.values())
    print(f"Max stops across all route-directions: {max_stops}")

    def pad_to_max(matrix: np.ndarray, current_stops: int) -> np.ndarray:
        if current_stops < max_stops:
            padding = np.zeros((matrix.shape[0], max_stops - current_stops))
            return np.concatenate([matrix, padding], axis=1)
        return matrix

    for rd_key in rd_keys:
        rd_df = df[df['route_direction_key'] == rd_key].copy()
        stops = stops_dict.get(rd_key, sorted(rd_df['stop_sequence'].unique()))
        n_stops = len(stops)

        # Trip単位で時間順にソート
        trip_order = rd_df.groupby('trip_key')['scheduled_arrival_time'].min().sort_values().index.tolist()

        if not use_lag_features and len(trip_order) <= effective_n_past:
            continue

        # 1. 遅延パターン (trip x stop)
        delay_pivot = rd_df.pivot_table(
            index='trip_key', columns='stop_sequence',
            values='arrival_delay', aggfunc='first'
        )
        delay_pivot = delay_pivot.reindex(index=trip_order, columns=stops).ffill(axis=1).fillna(0)
        delay_values = pad_to_max(delay_pivot.values, n_stops)

        if use_lag_features:
            lag_tensor_list = []
            for col in lag_columns:
                lag_pivot = rd_df.pivot_table(
                    index='trip_key', columns='stop_sequence',
                    values=col, aggfunc='first'
                )
                lag_pivot = lag_pivot.reindex(index=trip_order, columns=stops).fillna(0)
                lag_values = pad_to_max(lag_pivot.values, n_stops)
                lag_tensor_list.append(lag_values)
            lag_tensor = np.stack(lag_tensor_list, axis=1)  # (num_trips, effective_n_past, max_stops)
        else:
            lag_tensor = None

        # 2. 時間・天候・アラート特徴量 + route_direction_encoded
        trip_features = rd_df.groupby('trip_key')[feature_cols + ['route_direction_encoded']].first()
        trip_features = trip_features.reindex(index=trip_order).fillna(0)

        # シーケンス作成
        start_idx = 0 if use_lag_features else effective_n_past
        for i in range(start_idx, len(trip_order)):
            if use_lag_features:
                past_delays = lag_tensor[i]
            else:
                past_delays = delay_values[i-effective_n_past:i]

            # 予測対象便の特徴量
            target_features = trip_features.iloc[i].values  # (n_features,)

            # ★ 集約特徴量 ★
            past_mean = past_delays.mean()
            past_std = past_delays.std()
            past_trend = past_delays[-1].mean() - past_delays[0].mean()
            past_max = past_delays.max()
            agg_features = np.array([past_mean, past_std, past_trend, past_max])

            # 予測対象の遅延
            target_delay = delay_values[i]  # (max_stops,)

            all_X_delays.append(past_delays)
            all_X_features.append(target_features)
            all_X_agg.append(agg_features)
            all_y.append(target_delay)
            all_meta.append(trip_order[i])

    X_delays = np.array(all_X_delays)  # (N, n_past_trips, max_stops)
    X_features = np.array(all_X_features)  # (N, n_features)
    X_agg = np.array(all_X_agg)  # (N, 4)
    y = np.array(all_y)  # (N, max_stops)

    print(f"\nTotal X_delays shape: {X_delays.shape}")
    print(f"Total X_features shape: {X_features.shape}")
    print(f"Total X_agg shape: {X_agg.shape}")
    print(f"Total y shape: {y.shape}")

    return X_delays, X_features, X_agg, y, all_meta, stops_dict, max_stops