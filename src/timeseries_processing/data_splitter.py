"""
データ分割クラス
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class DataSplitter:
    """データ分割クラス"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def reshape_for_convlstm(self, X, target_height=1, target_width=None):
        """
        ConvLSTM2D用にデータを(samples, timesteps, height, width, channels)形式に変換
        
        Args:
            X (np.array): 入力データ
            target_height (int): 高さ
            target_width (int): 幅（Noneの場合は特徴量数）
            
        Returns:
            np.array: reshape済みデータ
        """
        if target_width is None:
            target_width = X.shape[2]  # 特徴量数
        
        # (samples, timesteps, features) -> (samples, timesteps, height, width, channels)
        X_reshaped = X.reshape(X.shape[0], X.shape[1], target_height, target_width, 1)
        return X_reshaped
    
    def train_test_split_by_route_direction(self, X, y, route_direction_info, 
                                          train_ratio=0.8, random_state=42):
        """
        route_direction別でのグループ分割（データリークを防ぐ）
        
        Args:
            X (np.array): 入力データ
            y (np.array): 目標データ
            route_direction_info (list): 各シーケンスのroute_direction情報
            train_ratio (float): 訓練データの割合
            random_state (int): 乱数シード
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test, train_route_dirs, test_route_dirs)
        """
        # 乱数シードを設定
        np.random.seed(random_state)
        
        # ユニークなroute_direction取得
        unique_route_dirs = list(set(route_direction_info))
        print(f"Total unique route_directions: {len(unique_route_dirs)}")
        
        # ランダムシャッフル
        np.random.shuffle(unique_route_dirs)
        
        # train/test分割
        train_count = int(len(unique_route_dirs) * train_ratio)
        train_route_dirs = unique_route_dirs[:train_count]
        test_route_dirs = unique_route_dirs[train_count:]
        
        print(f"Train route_directions: {len(train_route_dirs)}")
        print(f"Test route_directions: {len(test_route_dirs)}")
        
        # インデックス分割
        train_indices = [i for i, rd in enumerate(route_direction_info) if rd in train_route_dirs]
        test_indices = [i for i, rd in enumerate(route_direction_info) if rd in test_route_dirs]
        
        # データ分割
        X_train = X[train_indices]
        X_test = X[test_indices]
        y_train = y[train_indices]
        y_test = y[test_indices]
        
        print(f"Train sequences: {len(X_train)}")
        print(f"Test sequences: {len(X_test)}")
        
        return X_train, X_test, y_train, y_test, train_route_dirs, test_route_dirs
    
    def train_test_split_by_route_direction_stratified(self, X, y, route_direction_info, 
                                                       train_ratio=0.8, random_state=42):
        """
        route_direction別での層化分割（各route_directionからtrain/testを分割）
        
        Args:
            X (np.array): 入力データ
            y (np.array): 目標データ
            route_direction_info (list): 各シーケンスのroute_direction情報
            train_ratio (float): 訓練データの割合
            random_state (int): 乱数シード
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test, train_indices, test_indices)
        """
        # 乱数シードを設定
        np.random.seed(random_state)
        
        # ユニークなroute_direction取得
        unique_route_dirs = list(set(route_direction_info))
        # print(f"Total unique route_directions: {len(unique_route_dirs)}")
        
        train_indices = []
        test_indices = []
        
        # 各route_directionごとに分割
        for route_dir in unique_route_dirs:
            # このroute_directionに属するインデックスを取得
            route_indices = [i for i, rd in enumerate(route_direction_info) if rd == route_dir]
            
            # ランダムシャッフル
            route_indices_shuffled = np.array(route_indices)
            np.random.shuffle(route_indices_shuffled)
            
            # train/test分割
            split_point = int(len(route_indices_shuffled) * train_ratio)
            train_indices.extend(route_indices_shuffled[:split_point].tolist())
            test_indices.extend(route_indices_shuffled[split_point:].tolist())
        
        # numpy配列に変換
        train_indices = np.array(train_indices)
        test_indices = np.array(test_indices)
        
        # データ分割
        X_train = X[train_indices]
        X_test = X[test_indices]
        y_train = y[train_indices]
        y_test = y[test_indices]
        
        # print(f"Train sequences: {len(X_train)} ({len(X_train)/(len(X_train)+len(X_test)):.1%})")
        # print(f"Test sequences: {len(X_test)} ({len(X_test)/(len(X_train)+len(X_test)):.1%})")
        
        # 各セットに含まれるroute_directionを確認
        train_route_dirs = list(set([route_direction_info[i] for i in train_indices]))
        test_route_dirs = list(set([route_direction_info[i] for i in test_indices]))
        # print(f"Train contains {len(train_route_dirs)} route_directions")
        # print(f"Test contains {len(test_route_dirs)} route_directions")
        
        return X_train, X_test, y_train, y_test, train_route_dirs, test_route_dirs
    def validate_split(self, X_train, X_test, y_train, y_test, route_direction_info=None, 
                      train_route_dirs=None, test_route_dirs=None):
        """
        分割結果の検証
        
        Args:
            X_train, X_test, y_train, y_test: 分割されたデータ
            route_direction_info (list): route_direction情報
            train_route_dirs (list): 訓練用route_direction
            test_route_dirs (list): テスト用route_direction
            
        Returns:
            dict: 検証結果
        """
        validation_results = {}
        
        # 基本的な形状チェック
        validation_results['train_shape'] = {
            'X': X_train.shape,
            'y': y_train.shape
        }
        validation_results['test_shape'] = {
            'X': X_test.shape,
            'y': y_test.shape
        }
        
        # データサイズチェック
        total_samples = len(X_train) + len(X_test)
        train_ratio = len(X_train) / total_samples
        validation_results['split_ratio'] = {
            'train': train_ratio,
            'test': 1 - train_ratio,
            'total_samples': total_samples
        }
        
        validation_results['route_direction_stats'] = {
            'train_routes': len(train_route_dirs),
            'test_routes': len(test_route_dirs),
            'total_unique_routes': len(set(train_route_dirs + test_route_dirs))
        }
        
        # Helper function to check for NaN values safely
        def safe_isnan_check(arr):
            """Check for NaN values, handling non-numeric types."""
            if arr is None:
                return False
            try:
                # For numeric types
                if np.issubdtype(arr.dtype, np.number):
                    return np.isnan(arr).any()
                # For object/string types, check for None or NaN objects
                elif arr.dtype == object:
                    return any(x is None or (isinstance(x, float) and np.isnan(x)) 
                              for x in arr.flat)
                else:
                    return False
            except (TypeError, AttributeError):
                return False
        
        # NaNチェック
        validation_results['nan_check'] = {
            'X_train_has_nan': safe_isnan_check(X_train),
            'X_test_has_nan': safe_isnan_check(X_test),
            'y_train_has_nan': safe_isnan_check(y_train),
            'y_test_has_nan': safe_isnan_check(y_test)
        }
        
        return validation_results
    
    def print_split_summary(self, validation_results):
        """
        分割結果のサマリー表示
        
        Args:
            validation_results (dict): validate_splitの結果
        """
        print("=== Data Split Validation Summary ===")
        
        # 形状情報
        print(f"Train data: X{validation_results['train_shape']['X']}, y{validation_results['train_shape']['y']}")
        print(f"Test data: X{validation_results['test_shape']['X']}, y{validation_results['test_shape']['y']}")
        
        # 分割比率
        split_info = validation_results['split_ratio']
        print(f"Split ratio: Train {split_info['train']:.1%}, Test {split_info['test']:.1%}")
        print(f"Total samples: {split_info['total_samples']}")
        
        # NaNチェック結果
        nan_info = validation_results['nan_check']
        has_any_nan = any(nan_info.values())
        if has_any_nan:
            print("⚠️ WARNING: NaN values detected in data!")
            for key, has_nan in nan_info.items():
                if has_nan:
                    print(f"  - {key}: Contains NaN")
        else:
            print("✅ No NaN values detected")
        
        print("=" * 40)
