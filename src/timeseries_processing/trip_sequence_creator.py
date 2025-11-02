"""
Trip-based Sequence Creator
個別のバス（trip_id）単位で時系列シーケンスを作成
上流停留所の遅延（prev_stop_delay）を正しく活用できる
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class TripSequenceCreator:
    """
    Trip単位でシーケンス作成

    従来のSequenceCreator（route_id + direction_id）との違い:
    - route-based: 同じルート・方向の異なるバスを時系列で並べる
    - trip-based: 1つのバス（trip_id）の停留所を時系列で並べる

    メリット:
    - prev_stop_delay（上流停留所遅延）が正しく機能
    - 空間的伝播（上流→下流）を学習可能

    デメリット:
    - シーケンス長が短い（8-30停留所）
    - シーケンス数が多い
    """

    def __init__(self, input_timesteps=8, output_timesteps=3, feature_groups=None):
        """
        Parameters:
        -----------
        input_timesteps : int
            入力シーケンス長（停留所数）
        output_timesteps : int
            出力シーケンス長（停留所数）
        feature_groups : dict
            特徴量グループ定義
        """
        self.input_timesteps = input_timesteps
        self.output_timesteps = output_timesteps
        self.feature_groups = feature_groups

        print(f"Initialized TripSequenceCreator (trip-based approach)")
        print(f"  Input: {input_timesteps} stops")
        print(f"  Output: {output_timesteps} stops")
        print(f"  Feature groups: {list(self.feature_groups.keys())}")

    def get_all_features_from_groups(self):
        """特徴量グループからすべての特徴量リストを取得"""
        all_features = []
        for k, v in self.feature_groups.items():
            if k != 'target':
                all_features.extend(v)
        return all_features

    def create_trip_sequences(self, data, target_col='arrival_delay',
                              min_stops=None, spatial_organization=True):
        """
        Trip単位でシーケンスを作成

        Parameters:
        -----------
        data : pd.DataFrame
            入力データ（trip_id, stop_sequence, arrival_delay等を含む）
        target_col : str
            目的変数のカラム名
        min_stops : int
            最小停留所数（これ以下のトリップは除外）
        spatial_organization : bool
            ConvLSTM用の空間配置を有効化

        Returns:
        --------
        X : np.array
            入力シーケンス (samples, timesteps, features)
        y : np.array
            出力シーケンス (samples, output_timesteps)
        trip_info : pd.DataFrame
            各シーケンスのtrip情報
        features : list
            使用した特徴量リスト
        group_info : dict
            特徴量グループ情報
        """
        if min_stops is None:
            min_stops = self.input_timesteps + self.output_timesteps

        print(f"\n=== Trip-based Sequence Creation ===")
        print(f"Total records: {len(data):,}")
        print(f"Unique trips: {data['trip_id'].nunique():,}")

        # 特徴量リスト取得
        all_features = self.get_all_features_from_groups()
        available_features = [f for f in all_features if f in data.columns]

        if target_col not in available_features:
            available_features.append(target_col)

        print(f"Available features: {len(available_features)}")

        # 空間配置
        if spatial_organization:
            organized_features, group_info = self._organize_features_spatially(available_features)
        else:
            organized_features = available_features
            group_info = None

        # Trip単位でグループ化
        X_list = []
        y_list = []
        trip_info_list = []

        target_idx = organized_features.index(target_col)

        for trip_id, trip_data in data.groupby('trip_id'):
            # stop_sequenceでソート
            trip_data = trip_data.sort_values('stop_sequence')

            # 停留所数チェック
            n_stops = len(trip_data)
            if n_stops < min_stops:
                continue

            # 特徴量抽出
            features_array = trip_data[organized_features].values

            # スライディングウィンドウでシーケンス作成
            for i in range(n_stops - self.input_timesteps - self.output_timesteps + 1):
                # 入力: i ~ i+input_timesteps
                X_seq = features_array[i:i+self.input_timesteps, :]

                # 出力: i+input_timesteps ~ i+input_timesteps+output_timesteps
                y_seq = features_array[i+self.input_timesteps:
                                       i+self.input_timesteps+self.output_timesteps,
                                       target_idx]

                X_list.append(X_seq)
                y_list.append(y_seq)

                # Trip情報保存
                trip_info_list.append({
                    'trip_id': trip_id,
                    'route_id': trip_data.iloc[i]['route_id'],
                    'direction_id': trip_data.iloc[i]['direction_id'],
                    'start_stop_sequence': trip_data.iloc[i]['stop_sequence'],
                    'end_stop_sequence': trip_data.iloc[i+self.input_timesteps+self.output_timesteps-1]['stop_sequence']
                })

        X = np.array(X_list)
        y = np.array(y_list)
        trip_info = pd.DataFrame(trip_info_list)

        print(f"\n=== Sequence Creation Results ===")
        print(f"Total sequences: {len(X):,}")
        print(f"Trips used: {trip_info['trip_id'].nunique():,}")
        print(f"X shape: {X.shape} (samples, timesteps={self.input_timesteps}, features={len(organized_features)})")
        print(f"y shape: {y.shape} (samples, output_timesteps={self.output_timesteps})")

        if group_info:
            print(f"\n=== Feature Groups (ConvLSTM Width Dimension) ===")
            for group_name, info in group_info.items():
                print(f"{group_name}: {info['features']}")
                print(f"  Indices: [{info['start_idx']}:{info['end_idx']}], Size: {info['size']}")

        return X, y, trip_info, organized_features, group_info

    def _organize_features_spatially(self, feature_cols):
        """ConvLSTM用に特徴量を空間的に配置"""
        organized_features = []
        group_info = {}
        current_idx = 0

        for group_name, features in self.feature_groups.items():
            if group_name == 'target':
                continue

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

        return organized_features, group_info


if __name__ == "__main__":
    # テスト用
    print("TripSequenceCreator module loaded successfully")
    print("\nUsage:")
    print("  from src.timeseries_processing.trip_sequence_creator import TripSequenceCreator")
    print("  creator = TripSequenceCreator(input_timesteps=8, output_timesteps=3)")
    print("  X, y, trip_info, features, group_info = creator.create_trip_sequences(df)")