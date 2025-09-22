import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class DataPreprocessor:
    def __init__(self):
        pass
    
    def show_missing_data_summary(self, data):
        table = pd.DataFrame(columns=['Missing Count', 'Missing Percentage'])
        for col in data.columns:
            missing_count = int(data[col].isnull().sum())
            missing_percentage = f'{round((missing_count / len(data)) * 100, 1)}%'
            table.loc[col] = (missing_count, missing_percentage)
        return table
    
    def delete_missing_values(self, data, columns):
        for col in columns:
            data = data.dropna(subset=[col])
        return data
    
    def remove_outliers_mad(self, df, column, threshold=3):
        if column not in df.columns or df[column].isna().all():
            return df
        
        median = df[column].median()
        mad = (df[column] - median).abs().median()
        
        if mad == 0:
            return df
        
        outlier_mask = (df[column] - median).abs() <= threshold * mad
        removed_count = len(df) - outlier_mask.sum()
        print(f"  {column}: Removed {removed_count} outliers using MAD method")
        return df[outlier_mask]
    
    def clean_gtfs_anomalies(df, delay_threshold_minutes=15):
        """
        GTFS異常値の検出とクリーニング
        
        Args:
            df: GTFSデータフレーム
            delay_threshold_minutes: 異常と判定する遅延時間の閾値（分）
        """
        # 異常な早着/遅延の検出
        delay_threshold_seconds = delay_threshold_minutes * 60
        
        # 異常値フラグの作成
        df['is_anomaly'] = (
            (df['arrival_delay'] < -delay_threshold_seconds) |  # 大幅早着
            (df['arrival_delay'] > delay_threshold_seconds * 2)  # 大幅遅延
        )
        
        # 時刻の逆転チェック
        df['time_reversal'] = df['datetime'].diff() < pd.Timedelta(0)
        
        # 総合的な異常判定
        df['should_exclude'] = (
            df['is_anomaly'] | 
            df['impossible_speed'] | 
            df['time_reversal']
        )
        
        return df
    
    def apply_graduated_filtering(df):
        """
        段階的フィルタリングの適用
        """
        # レベル1: 明らかな異常値を除外
        level1_clean = df[~df['should_exclude']].copy()
        
        # レベル2: 統計的外れ値の検出
        delay_mean = level1_clean['arrival_delay'].mean()
        delay_std = level1_clean['arrival_delay'].std()
        
        level1_clean['is_outlier'] = np.abs(
            (level1_clean['arrival_delay'] - delay_mean) / delay_std
        ) > 3  # 3σ以上を外れ値とする
        
        level2_clean = level1_clean[~level1_clean['is_outlier']].copy()
        
        return level1_clean, level2_clean

    def get_realistic_bus_thresholds(self):
        """
        バス運行の現実的な閾値設定
        TransLinkの運行特性を考慮
        """
        return {
            # 早着閾値（厳しく設定）
            'early_threshold_minor': 120,      # 2分早着（軽微）
            'early_threshold_major': 300,      # 5分早着（重大）
            'early_threshold_severe': 600,     # 10分早着（異常）
            
            # 遅延閾値（現実的に設定）
            'delay_threshold_minor': 300,      # 5分遅延（軽微）
            'delay_threshold_major': 900,      # 15分遅延（重大）
            'delay_threshold_severe': 1800,    # 30分遅延（異常）
            
            # 時間帯別調整係数
            'rush_hour_multiplier': 1.5,       # ラッシュ時は1.5倍まで許容
            'night_hour_multiplier': 0.8,      # 夜間は厳しく評価
        }
    
    def clean_gtfs_with_asymmetric_thresholds(self, df):
        """
        非対称閾値を使用した現実的な異常値検出
        """
        df = df.copy()
        thresholds = self.get_realistic_bus_thresholds()
        df['hour_of_day'] = df['datetime'].dt.hour
        
        # 2. 時間帯の分類
        df['is_rush_hour'] = df['hour_of_day'].isin([7, 8, 9, 17, 18, 19])
        df['is_night_hour'] = df['hour_of_day'].isin([22, 23, 0, 1, 2, 3, 4, 5])
        
        # 3. 時間帯別閾値調整
        df['delay_threshold_adjusted'] = thresholds['delay_threshold_major']
        df['early_threshold_adjusted'] = thresholds['early_threshold_major']
        
        # ラッシュ時：遅延許容範囲を拡大
        rush_mask = df['is_rush_hour']
        df.loc[rush_mask, 'delay_threshold_adjusted'] *= thresholds['rush_hour_multiplier']
        
        # 夜間：両方向とも厳しく評価
        night_mask = df['is_night_hour'] 
        df.loc[night_mask, 'delay_threshold_adjusted'] *= thresholds['night_hour_multiplier']
        df.loc[night_mask, 'early_threshold_adjusted'] *= thresholds['night_hour_multiplier']
        
        # 4. 非対称な異常値検出
        df['is_minor_early'] = df['arrival_delay'] < -thresholds['early_threshold_minor']
        df['is_major_early'] = df['arrival_delay'] < -df['early_threshold_adjusted']
        df['is_severe_early'] = df['arrival_delay'] < -thresholds['early_threshold_severe']
        
        df['is_minor_delay'] = df['arrival_delay'] > thresholds['delay_threshold_minor']
        df['is_major_delay'] = df['arrival_delay'] > df['delay_threshold_adjusted']
        df['is_severe_delay'] = df['arrival_delay'] > thresholds['delay_threshold_severe']
        
        # 6. 総合的な異常判定（段階的）
        df['anomaly_level'] = 0  # 正常
        
        # レベル1: 軽微な異常（データ保持、要注意）
        df.loc[df['is_minor_early'] | df['is_minor_delay'], 'anomaly_level'] = 1
        
        # レベル2: 重大な異常（データ保持、重み調整）
        df.loc[df['is_major_early'] | df['is_major_delay'], 'anomaly_level'] = 2
        
        # レベル3: 異常（除外推奨）
        df.loc[df['is_severe_early'] | df['is_severe_delay'], 'anomaly_level'] = 3
        
        # 除外フラグ（レベル2以上除外）
        df['should_exclude'] = df['anomaly_level'] >= 2
        
        return df