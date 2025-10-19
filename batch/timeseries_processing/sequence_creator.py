import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class SequenceCreator:
    def __init__(self, input_timesteps=8, output_timesteps=3, feature_groups=None):
        self.input_timesteps = input_timesteps
        self.output_timesteps = output_timesteps
        self.feature_groups = feature_groups
        
        print(f"Initialized SequenceCreator with feature_groups: {list(self.feature_groups.keys())}")
    
    def get_all_features_from_groups(self):
        all_features = []
        for k,v in self.feature_groups.items():
            if k != 'target':
                all_features.extend(v)
        
        return all_features
    
    def organize_features_spatially(self, feature_cols):
        organized_features = []
        group_info = {}
        current_idx = 0
        
        print("=== Feature Spatial Organization for ConvLSTM ===")
        
        for group_name, features in self.feature_groups.items():
            group_features = []
            start_idx = current_idx
            
            for feature in features:
                if feature in feature_cols:
                    organized_features.append(feature)
                    group_features.append(feature)
                    current_idx += 1
            
            if group_features:
                group_info[group_name] = {
                    'features': group_features,
                    'start_idx': start_idx,
                    'end_idx': current_idx,
                    'size': len(group_features)
                }
                print(f"{group_name.capitalize()} group: {group_features} (indices {start_idx}-{current_idx-1})")
        
        print(f"Total organized features: {len(organized_features)}")
        print(f"Spatial arrangement: {organized_features}")
        
        return organized_features, group_info
    
    def create_route_direction_aware_sequences(self, data, target_col=None, feature_cols=None, 
                                              route_col='route_id', direction_col='direction_id',
                                              spatial_organization=True):
        """
        route_id + direction_id別の時系列シーケンスを作成
        
        Args:
            data (pd.DataFrame): 入力データ
            target_col (str): 予測対象カラム名（Noneの場合は'arrival_delay'を使用）
            feature_cols (list): 特徴量カラムリスト（Noneの場合はfeature_groupsから自動生成）
            route_col (str): 路線IDカラム名
            direction_col (str): 方向IDカラム名
            spatial_organization (bool): ConvLSTM用の空間配置を使用するか
            
        Returns:
            tuple: (X配列, y配列, route_direction情報, 使用特徴量リスト, グループ情報)
        """
        X_all, y_all = [], []
        route_direction_info = []  # route_id + direction_id情報を保持
        
        # デフォルト値の設定
        if target_col is None:
            target_col = 'arrival_delay'
        
        if feature_cols is None:
            feature_cols = self.get_all_features_from_groups()
            print(f"Using feature_groups to generate feature list: {feature_cols}")
        
        print(f"=== Optimized Sequence Creation by Route ID + Direction ID ===")
        print(f"Input time series length: {self.input_timesteps} hours")
        print(f"Prediction time series length: {self.output_timesteps} hours")
        print(f"Target column: {target_col}")
        print(f"Feature columns: {feature_cols}")
        print(f"Spatial organization: {spatial_organization}")
        
        # 特徴量の空間配置（ConvLSTM用）
        if spatial_organization:
            organized_features, group_info = self.organize_features_spatially(feature_cols)
            # 利用可能な特徴量のフィルタリング（空間配置順序を保持）
            available_features = [col for col in organized_features if col in data.columns]
            missing_features = [col for col in organized_features if col not in data.columns]
        else:
            # 従来の順序
            available_features = [col for col in feature_cols if col in data.columns]
            missing_features = [col for col in feature_cols if col not in data.columns]
            group_info = None
        
        if missing_features:
            print(f"Warning: Missing features will be skipped: {missing_features}")
        
        print(f"Using features (in spatial order): {available_features}")
        
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
                    # 利用可能な特徴量のみを使用（空間配置順序）
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
            
            if spatial_organization and group_info:
                print(f"\n=== Spatial Organization Summary ===")
                for group_name, info in group_info.items():
                    print(f"{group_name.capitalize()}: {info['features']} (width indices {info['start_idx']}-{info['end_idx']-1})")
            
            return X_combined, y_combined, route_direction_info, available_features, group_info
        else:
            print("\nSequence creation failed")
            return np.array([]), np.array([]), [], available_features, group_info
