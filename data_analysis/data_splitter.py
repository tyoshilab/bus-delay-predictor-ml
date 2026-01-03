"""
時系列データ分割・交差検証モジュール

このモジュールは以下の機能を提供:
- 時系列データの train/valid/test 分割
- Sliding Window / Expanding Window 交差検証
- 分割の検証・可視化
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Generator, Optional, Dict, Any
import warnings
warnings.filterwarnings('ignore')


class TimeSeriesSplit:
    """
    時系列交差検証クラス

    Sliding Window: 固定サイズの訓練ウィンドウを移動
    Expanding Window: 訓練データを累積的に拡大

    Example:
        >>> tscv = TimeSeriesSplit(n_splits=5, method='expanding')
        >>> for train_dates, test_dates in tscv.split(unique_dates):
        ...     print(f"Train: {train_dates[0]} - {train_dates[-1]}")
        ...     print(f"Test: {test_dates[0]} - {test_dates[-1]}")
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_size: Optional[int] = None,
        test_size: int = 1,
        gap: int = 0,
        method: str = 'expanding'
    ):
        """
        Args:
            n_splits: 分割数
            train_size: 訓練データのサイズ（Sliding Windowの場合必須、Expandingの場合は初期サイズ）
            test_size: テストデータのサイズ（期間数）
            gap: 訓練とテストの間のギャップ（データリーク防止）
            method: 'sliding' または 'expanding'
        """
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
        self.gap = gap
        self.method = method

        if method not in ['sliding', 'expanding']:
            raise ValueError("method must be 'sliding' or 'expanding'")

    def split(
        self,
        dates: np.ndarray,
        groups: Optional[np.ndarray] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        時系列分割のインデックスを生成

        Args:
            dates: 日付配列（ソート済み、ユニーク）
            groups: グループ情報（オプション）

        Yields:
            (train_dates, test_dates) のタプル
        """
        n_dates = len(dates)

        if self.method == 'sliding':
            if self.train_size is None:
                raise ValueError("train_size is required for sliding window")

            min_required = self.train_size + self.gap + self.test_size
            if n_dates < min_required:
                raise ValueError(f"Not enough data. Need at least {min_required} periods, got {n_dates}")

            # 開始位置を計算
            max_start = n_dates - self.train_size - self.gap - self.test_size
            step = max(1, max_start // (self.n_splits - 1)) if self.n_splits > 1 else 1

            for i in range(self.n_splits):
                start = i * step
                train_end = start + self.train_size
                test_start = train_end + self.gap
                test_end = test_start + self.test_size

                if test_end > n_dates:
                    break

                train_dates = dates[start:train_end]
                test_dates = dates[test_start:test_end]

                yield train_dates, test_dates

        else:  # expanding
            initial_train = self.train_size if self.train_size else n_dates // (self.n_splits + 1)

            min_required = initial_train + self.gap + self.test_size
            if n_dates < min_required:
                raise ValueError(f"Not enough data. Need at least {min_required} periods, got {n_dates}")

            # 各foldでテストデータを何期間進めるか
            remaining = n_dates - initial_train - self.gap
            step = remaining // self.n_splits

            for i in range(self.n_splits):
                train_end = initial_train + (i * step)
                test_start = train_end + self.gap
                test_end = min(test_start + self.test_size, n_dates)

                if test_end > n_dates:
                    break

                train_dates = dates[:train_end]
                test_dates = dates[test_start:test_end]

                yield train_dates, test_dates

    def get_n_splits(self) -> int:
        """分割数を返す"""
        return self.n_splits


def temporal_train_valid_test_split(
    df: pd.DataFrame,
    date_column: str = 'start_date',
    train_ratio: float = 0.7,
    valid_ratio: float = 0.15,
    test_ratio: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    時系列データを時間軸で train/valid/test に分割

    Args:
        df: 入力データフレーム
        date_column: 日付カラム名
        train_ratio: 訓練データの割合
        valid_ratio: 検証データの割合
        test_ratio: テストデータの割合

    Returns:
        (df_train, df_valid, df_test, split_info) のタプル
    """
    if abs(train_ratio + valid_ratio + test_ratio - 1.0) > 1e-6:
        raise ValueError("Ratios must sum to 1.0")

    # ユニークな日付を取得してソート
    unique_dates = sorted(df[date_column].unique())
    n_dates = len(unique_dates)

    # 分割インデックスを計算
    train_end_idx = int(n_dates * train_ratio)
    valid_end_idx = int(n_dates * (train_ratio + valid_ratio))

    # 日付で分割
    train_dates = unique_dates[:train_end_idx]
    valid_dates = unique_dates[train_end_idx:valid_end_idx]
    test_dates = unique_dates[valid_end_idx:]

    # データフレームを分割
    df_train = df[df[date_column].isin(train_dates)].copy()
    df_valid = df[df[date_column].isin(valid_dates)].copy()
    df_test = df[df[date_column].isin(test_dates)].copy()

    # 分割情報
    split_info = {
        'train_dates': list(train_dates),
        'valid_dates': list(valid_dates),
        'test_dates': list(test_dates),
        'train_date_range': (train_dates[0], train_dates[-1]) if train_dates else None,
        'valid_date_range': (valid_dates[0], valid_dates[-1]) if valid_dates else None,
        'test_date_range': (test_dates[0], test_dates[-1]) if test_dates else None,
        'train_samples': len(df_train),
        'valid_samples': len(df_valid),
        'test_samples': len(df_test),
        'train_ratio_actual': len(df_train) / len(df),
        'valid_ratio_actual': len(df_valid) / len(df),
        'test_ratio_actual': len(df_test) / len(df),
    }

    return df_train, df_valid, df_test, split_info


def print_split_info(split_info: Dict[str, Any]) -> None:
    """分割情報を表示"""
    print("=" * 50)
    print("Time Series Split Information")
    print("=" * 50)

    for name in ['train', 'valid', 'test']:
        date_range = split_info.get(f'{name}_date_range')
        samples = split_info.get(f'{name}_samples', 0)
        ratio = split_info.get(f'{name}_ratio_actual', 0)

        if date_range:
            print(f"\n{name.upper()}:")
            print(f"  Date range: {date_range[0]} ~ {date_range[1]}")
            print(f"  Samples: {samples:,} ({ratio:.1%})")

    print("=" * 50)


def save_split_data(
    df_train: pd.DataFrame,
    df_valid: pd.DataFrame,
    df_test: pd.DataFrame,
    split_info: Dict[str, Any],
    output_dir: str = 'data/processed_data',
    format: str = 'parquet'
) -> None:
    """
    分割データをファイルに保存

    Args:
        df_train: 訓練データ
        df_valid: 検証データ
        df_test: テストデータ
        split_info: 分割情報
        output_dir: 出力ディレクトリ
        format: 'parquet' または 'csv'
    """
    import os
    import json

    os.makedirs(output_dir, exist_ok=True)

    if format == 'parquet':
        # Ensure start_date is string before saving
        for df in [df_train, df_valid, df_test]:
            if 'start_date' in df.columns:
                df['start_date'] = df['start_date'].astype(str)
                
        df_train.to_parquet(f'{output_dir}/train.parquet', index=False)
        df_valid.to_parquet(f'{output_dir}/valid.parquet', index=False)
        df_test.to_parquet(f'{output_dir}/test.parquet', index=False)
    else:
        df_train.to_csv(f'{output_dir}/train.csv', index=False)
        df_valid.to_csv(f'{output_dir}/valid.csv', index=False)
        df_test.to_csv(f'{output_dir}/test.csv', index=False)

    # split_info を JSON 形式で保存（日付リストは文字列に変換）
    split_info_serializable = split_info.copy()
    for key in ['train_dates', 'valid_dates', 'test_dates']:
        if key in split_info_serializable:
            split_info_serializable[key] = [str(d) for d in split_info_serializable[key]]

    with open(f'{output_dir}/split_info.json', 'w') as f:
        json.dump(split_info_serializable, f, indent=2, default=str)

    print(f"Saved split data to {output_dir}/")
    print(f"  - train.{format}: {len(df_train):,} samples")
    print(f"  - valid.{format}: {len(df_valid):,} samples")
    print(f"  - test.{format}: {len(df_test):,} samples")
    print(f"  - split_info.json")


def load_split_data(
    input_dir: str = 'data/processed_data',
    format: str = 'parquet'
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    分割データをファイルから読み込み

    Args:
        input_dir: 入力ディレクトリ
        format: 'parquet' または 'csv'

    Returns:
        (df_train, df_valid, df_test, split_info) のタプル
    """
    import json

    if format == 'parquet':
        df_train = pd.read_parquet(f'{input_dir}/train.parquet')
        df_valid = pd.read_parquet(f'{input_dir}/valid.parquet')
        df_test = pd.read_parquet(f'{input_dir}/test.parquet')
    else:
        df_train = pd.read_csv(f'{input_dir}/train.csv')
        df_valid = pd.read_csv(f'{input_dir}/valid.csv')
        df_test = pd.read_csv(f'{input_dir}/test.csv')

    with open(f'{input_dir}/split_info.json', 'r') as f:
        split_info = json.load(f)

    return df_train, df_valid, df_test, split_info


class TimeSeriesCrossValidator:
    """
    時系列交差検証を実行するクラス

    Example:
        >>> cv = TimeSeriesCrossValidator(n_splits=5, method='expanding')
        >>> for fold, (train_df, test_df) in enumerate(cv.split(df)):
        ...     model.fit(train_df)
        ...     score = model.evaluate(test_df)
        ...     print(f"Fold {fold}: {score}")
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_size: Optional[int] = None,
        test_size: int = 1,
        gap: int = 0,
        method: str = 'expanding',
        date_column: str = 'start_date'
    ):
        """
        Args:
            n_splits: 分割数
            train_size: 訓練データの日数（Sliding Windowの場合必須）
            test_size: テストデータの日数
            gap: 訓練とテストの間のギャップ（日数）
            method: 'sliding' または 'expanding'
            date_column: 日付カラム名
        """
        self.ts_split = TimeSeriesSplit(
            n_splits=n_splits,
            train_size=train_size,
            test_size=test_size,
            gap=gap,
            method=method
        )
        self.date_column = date_column
        self.n_splits = n_splits

    def split(
        self,
        df: pd.DataFrame
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        データフレームを時系列交差検証用に分割

        Args:
            df: 入力データフレーム

        Yields:
            (train_df, test_df) のタプル
        """
        unique_dates = np.array(sorted(df[self.date_column].unique()))

        for train_dates, test_dates in self.ts_split.split(unique_dates):
            train_df = df[df[self.date_column].isin(train_dates)].copy()
            test_df = df[df[self.date_column].isin(test_dates)].copy()
            yield train_df, test_df

    def get_fold_info(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        各foldの情報を取得

        Args:
            df: 入力データフレーム

        Returns:
            各foldの情報のリスト
        """
        unique_dates = np.array(sorted(df[self.date_column].unique()))
        fold_info = []

        for i, (train_dates, test_dates) in enumerate(self.ts_split.split(unique_dates)):
            train_df = df[df[self.date_column].isin(train_dates)]
            test_df = df[df[self.date_column].isin(test_dates)]

            fold_info.append({
                'fold': i,
                'train_date_range': (train_dates[0], train_dates[-1]),
                'test_date_range': (test_dates[0], test_dates[-1]),
                'train_n_dates': len(train_dates),
                'test_n_dates': len(test_dates),
                'train_samples': len(train_df),
                'test_samples': len(test_df)
            })

        return fold_info

    def print_fold_summary(self, df: pd.DataFrame) -> None:
        """各foldのサマリーを表示"""
        fold_info = self.get_fold_info(df)

        print("=" * 70)
        print(f"Time Series Cross-Validation Summary ({self.ts_split.method.upper()})")
        print("=" * 70)

        for info in fold_info:
            print(f"\nFold {info['fold']}:")
            print(f"  Train: {info['train_date_range'][0]} ~ {info['train_date_range'][1]} "
                  f"({info['train_n_dates']} days, {info['train_samples']:,} samples)")
            print(f"  Test:  {info['test_date_range'][0]} ~ {info['test_date_range'][1]} "
                  f"({info['test_n_dates']} days, {info['test_samples']:,} samples)")

        print("=" * 70)
