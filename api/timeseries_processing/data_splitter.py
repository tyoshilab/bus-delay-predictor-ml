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
    
    def train_test_split_temporal(self, X, y, train_ratio=0.9):
        """
        時系列データの時間順での分割
        
        Args:
            X (np.array): 入力データ
            y (np.array): 目標データ
            train_ratio (float): 訓練データの割合
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        split_idx = int(len(X) * train_ratio)
        
        X_train = X[:split_idx]
        X_test = X[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]
        
        return X_train, X_test, y_train, y_test
    
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
    
    def train_test_split_sequence_aware(self, X, y, route_direction_info, 
                                       split_method='route_aware', train_ratio=0.8, 
                                       random_state=42):
        """
        シーケンス情報を考慮した分割
        
        Args:
            X (np.array): 入力データ
            y (np.array): 目標データ
            route_direction_info (list): 各シーケンスのroute_direction情報
            split_method (str): 分割方法 ('route_aware', 'random', 'temporal')
            train_ratio (float): 訓練データの割合
            random_state (int): 乱数シード
            
        Returns:
            tuple: 分割方法に応じた結果
        """
        if split_method == 'route_aware':
            return self.train_test_split_by_route_direction(
                X, y, route_direction_info, train_ratio, random_state
            )
        elif split_method == 'random':
            return self.train_test_split_random_sequence(
                X, y, route_direction_info, train_ratio, random_state
            )
        elif split_method == 'temporal':
            return self.train_test_split_temporal(X, y, train_ratio)
        else:
            raise ValueError(f"Unknown split_method: {split_method}")
    
    def train_test_split_random_sequence(self, X, y, route_direction_info, 
                                        train_ratio=0.8, random_state=42):
        """
        ランダム分割（シーケンス単位）
        
        Args:
            X (np.array): 入力データ
            y (np.array): 目標データ
            route_direction_info (list): route_direction情報（記録用）
            train_ratio (float): 訓練データの割合
            random_state (int): 乱数シード
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        # 乱数シードを設定
        np.random.seed(random_state)
        
        # インデックスをランダムシャッフル
        indices = np.arange(len(X))
        np.random.shuffle(indices)
        
        # train/test分割
        train_count = int(len(indices) * train_ratio)
        train_indices = indices[:train_count]
        test_indices = indices[train_count:]
        
        # データ分割
        X_train = X[train_indices]
        X_test = X[test_indices]
        y_train = y[train_indices]
        y_test = y[test_indices]
        
        print(f"Random split - Train sequences: {len(X_train)}")
        print(f"Random split - Test sequences: {len(X_test)}")
        
        return X_train, X_test, y_train, y_test
    
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
        
        # route_direction重複チェック（route_aware分割の場合）
        if train_route_dirs is not None and test_route_dirs is not None:
            overlap = set(train_route_dirs) & set(test_route_dirs)
            validation_results['route_direction_overlap'] = {
                'has_overlap': len(overlap) > 0,
                'overlap_count': len(overlap),
                'overlapping_routes': list(overlap) if overlap else []
            }
            
            validation_results['route_direction_stats'] = {
                'train_routes': len(train_route_dirs),
                'test_routes': len(test_route_dirs),
                'total_unique_routes': len(set(train_route_dirs + test_route_dirs))
            }
        
        # NaNチェック
        validation_results['nan_check'] = {
            'X_train_has_nan': np.isnan(X_train).any(),
            'X_test_has_nan': np.isnan(X_test).any(),
            'y_train_has_nan': np.isnan(y_train).any(),
            'y_test_has_nan': np.isnan(y_test).any()
        }
        
        # 統計情報
        validation_results['statistics'] = {
            'X_train': {
                'mean': np.mean(X_train),
                'std': np.std(X_train),
                'min': np.min(X_train),
                'max': np.max(X_train)
            },
            'y_train': {
                'mean': np.mean(y_train),
                'std': np.std(y_train),
                'min': np.min(y_train),
                'max': np.max(y_train)
            }
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
        
        # Route_direction重複チェック結果
        if 'route_direction_overlap' in validation_results:
            overlap_info = validation_results['route_direction_overlap']
            if overlap_info['has_overlap']:
                print(f"⚠️ WARNING: Route direction overlap detected!")
                print(f"Overlapping routes: {overlap_info['overlapping_routes']}")
            else:
                print("✅ No route direction overlap (good for preventing data leakage)")
            
            route_stats = validation_results['route_direction_stats']
            print(f"Route directions: Train {route_stats['train_routes']}, Test {route_stats['test_routes']}")
        
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
