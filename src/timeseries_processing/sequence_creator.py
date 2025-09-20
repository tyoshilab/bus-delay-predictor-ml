"""
時系列シーケンス作成クラス
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class SequenceCreator:
    """時系列シーケンス作成クラス"""
    
    def __init__(self, input_timesteps=8, output_timesteps=3):
        """
        Args:
            input_timesteps (int): 入力シーケンス長
            output_timesteps (int): 出力シーケンス長
        """
        self.input_timesteps = input_timesteps
        self.output_timesteps = output_timesteps
    
    def create_route_direction_aware_sequences(self, data, target_col, feature_cols, 
                                              route_col='route_id', direction_col='direction_id'):
        """
        route_id + direction_id別の時系列シーケンスを作成
        
        Args:
            data (pd.DataFrame): 入力データ
            target_col (str): 予測対象カラム名
            feature_cols (list): 特徴量カラムリスト
            route_col (str): 路線IDカラム名
            direction_col (str): 方向IDカラム名
            
        Returns:
            tuple: (X配列, y配列, route_direction情報, 使用特徴量リスト)
        """
        X_all, y_all = [], []
        route_direction_info = []  # route_id + direction_id情報を保持
        
        print(f"=== Optimized Sequence Creation by Route ID + Direction ID ===")
        print(f"Input time series length: {self.input_timesteps} hours")
        print(f"Prediction time series length: {self.output_timesteps} hours")
        print(f"Available features: {feature_cols}")
        
        # 利用可能な特徴量のフィルタリング
        available_features = [col for col in feature_cols if col in data.columns]
        missing_features = [col for col in feature_cols if col not in data.columns]
        
        if missing_features:
            print(f"Warning: Missing features will be skipped: {missing_features}")
        
        print(f"Using features: {available_features}")
        
        # route_id + direction_idの組み合わせごとにシーケンスを作成
        total_sequences = 0
        for route_id in data[route_col].unique():
            for direction_id in data[data[route_col] == route_id][direction_col].unique():
                # 特定のroute_id + direction_idのデータを抽出
                route_direction_data = data[
                    (data[route_col] == route_id) & (data[direction_col] == direction_id)
                ].copy()
                
                # 時間順にソート
                route_direction_data = route_direction_data.sort_values('time_bucket').reset_index(drop=True)
                
                route_direction_key = f"{route_id}_{direction_id}"
                print(f"route_id {route_id}, direction_id {direction_id}: {len(route_direction_data)} records", end=" -> ")
                
                if len(route_direction_data) >= self.input_timesteps + self.output_timesteps:
                    # 利用可能な特徴量のみを使用
                    try:
                        features = route_direction_data[available_features].values
                        
                        X_route_dir, y_route_dir = [], []
                        
                        for i in range(len(features) - self.input_timesteps - self.output_timesteps + 1):
                            # 入力シーケンス（過去のデータ）
                            X_route_dir.append(features[i:i+self.input_timesteps])
                            
                            # 出力シーケンス（予測対象）
                            target_start = i + self.input_timesteps
                            target_end = target_start + self.output_timesteps
                            
                            # target_colのインデックスを取得
                            target_idx = available_features.index(target_col)
                            y_route_dir.append(features[target_start:target_end, target_idx])
                        
                        if len(X_route_dir) > 0:
                            X_route_dir = np.array(X_route_dir)
                            y_route_dir = np.array(y_route_dir)
                            
                            X_all.append(X_route_dir)
                            y_all.append(y_route_dir)
                            route_direction_info.extend([route_direction_key] * len(X_route_dir))
                            
                            total_sequences += len(X_route_dir)
                            print(f"{len(X_route_dir)} sequences generated")
                        else:
                            print("Sequence generation failed (insufficient data)")
                            
                    except Exception as e:
                        print(f"Error processing data: {str(e)}")
                else:
                    print(f"Sequence generation failed (minimum {self.input_timesteps + self.output_timesteps} records required)")
        
        if X_all:
            X_combined = np.concatenate(X_all, axis=0)
            y_combined = np.concatenate(y_all, axis=0)
            
            print(f"\nTotal sequences: {len(X_combined)}")
            print(f"X shape: {X_combined.shape}")
            print(f"y shape: {y_combined.shape}")
            print(f"Features used: {len(available_features)} out of {len(feature_cols)}")
            
            return X_combined, y_combined, route_direction_info, available_features
        else:
            print("\nSequence creation failed")
            return np.array([]), np.array([]), [], available_features
