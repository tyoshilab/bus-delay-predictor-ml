#!/usr/bin/env python3
"""
Climate Data Cleaner
バンクーバー気象データの欠損値処理と整形を行うスクリプト

このスクリプトはclean_climate.ipynbの内容をPythonファイル化したものです。
"""

import pandas as pd
import numpy as np
import math
import logging
from pathlib import Path
import argparse
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClimateDataCleaner:
    """気象データクリーニングクラス"""
    
    def __init__(self, input_file, output_file=None):
        """
        初期化
        
        Args:
            input_file (str): 入力CSVファイルパス
            output_file (str): 出力CSVファイルパス（Noneの場合は自動生成）
        """
        self.input_file = Path(input_file)
        if output_file:
            self.output_file = Path(output_file)
        else:
            # 自動でファイル名生成
            name_parts = self.input_file.stem.split('_')
            if 'filled' not in name_parts:
                name_parts.append('filled')
            output_name = '_'.join(name_parts) + '.csv'
            self.output_file = self.input_file.parent / output_name
        
        self.df = None
        self.original_missing_count = 0
        self.final_missing_count = 0
        
    def load_data(self):
        """データの読み込み"""
        try:
            logger.info(f"データ読み込み中: {self.input_file}")
            self.df = pd.read_csv(self.input_file)
            logger.info(f"データ読み込み完了: {len(self.df)}行, {len(self.df.columns)}列")
            
            # 元の欠損値数を記録
            self.original_missing_count = self.df.isnull().sum().sum()
            logger.info(f"元の欠損値数: {self.original_missing_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"データ読み込みエラー: {e}")
            return False
    
    def remove_unnecessary_columns(self):
        """不要な列の削除"""
        columns_to_drop = [
            "wind_dir", "wind_gust", "windchill", 
            "cloud_cover_4", "cloud_cover_10", "solar_radiation", 
            "health_index", "humidex"
        ]
        
        # 存在する列のみ削除
        existing_columns = [col for col in columns_to_drop if col in self.df.columns]
        
        if existing_columns:
            logger.info(f"不要な列を削除: {existing_columns}")
            self.df.drop(columns=existing_columns, inplace=True)
        else:
            logger.info("削除対象の列が見つかりませんでした")
    
    def analyze_missing_values(self):
        """欠損値の分析"""
        logger.info("=== 欠損値分析 ===")
        
        missing_stats = self.df.isnull().sum()
        missing_pct = (missing_stats / len(self.df)) * 100
        
        # 主要な気象指標の欠損値状況
        key_columns = ['wind_dir_10s', 'visibility', 'cloud_cover_8', 'relative_humidity', 'dew_point']
        
        for col in key_columns:
            if col in missing_stats and missing_stats[col] > 0:
                logger.info(f"{col}: {missing_stats[col]} missing ({missing_pct[col]:.1f}%)")
        
        # 同時欠損パターンの確認
        if all(col in self.df.columns for col in ['wind_dir_10s', 'visibility', 'cloud_cover_8']):
            simultaneous_missing = len(self.df[
                (self.df['wind_dir_10s'].isna()) & 
                (self.df['visibility'].isna()) & 
                (self.df['cloud_cover_8'].isna())
            ])
            logger.info(f"3つの指標が同時に欠損している行: {simultaneous_missing}")
    
    def fill_wind_direction_circular(self, col='wind_dir_10s'):
        """風向の欠損値を円形統計で補完"""
        if col not in self.df.columns:
            logger.warning(f"列 '{col}' が存在しません")
            return
        
        missing_count = self.df[col].isnull().sum()
        if missing_count == 0:
            logger.info(f"{col}: 欠損値なし")
            return
        
        logger.info(f"{col}の欠損値を円形平均で補完中... ({missing_count}個)")
        
        # 風向を弧度に変換
        wind_rad = np.radians(self.df[col])
        
        # 有効な風向データで円形平均を計算
        valid_winds = wind_rad[~np.isnan(wind_rad)]
        
        if len(valid_winds) > 0:
            # sin, cosの平均を計算
            sin_mean = np.nanmean(np.sin(valid_winds))
            cos_mean = np.nanmean(np.cos(valid_winds))
            
            # 円形平均を計算
            circular_mean_rad = np.arctan2(sin_mean, cos_mean)
            circular_mean_deg = np.degrees(circular_mean_rad)
            
            # 0-360度の範囲に正規化
            if circular_mean_deg < 0:
                circular_mean_deg += 360
            
            # 欠損値を補完
            self.df[col] = self.df[col].fillna(circular_mean_deg)
            logger.info(f"{col}: 円形平均値 {circular_mean_deg:.1f}°で補完完了")
        else:
            logger.warning(f"{col}: 有効なデータがありません")
    
    def fill_visibility_interpolation(self, col='visibility'):
        """視程の欠損値を線形補間で補完"""
        if col not in self.df.columns:
            logger.warning(f"列 '{col}' が存在しません")
            return
        
        missing_count = self.df[col].isnull().sum()
        if missing_count == 0:
            logger.info(f"{col}: 欠損値なし")
            return
        
        logger.info(f"{col}の欠損値を線形補間で補完中... ({missing_count}個)")
        
        # 線形補間
        self.df[col] = self.df[col].interpolate(method='linear')
        
        # 先頭・末尾の残存欠損値を前方・後方補完
        self.df[col] = self.df[col].ffill().bfill()
        
        logger.info(f"{col}: 線形補間による補完完了")
    
    def fill_cloud_cover_mode(self, col='cloud_cover_8'):
        """雲量の欠損値を最頻値で補完"""
        if col not in self.df.columns:
            logger.warning(f"列 '{col}' が存在しません")
            return
        
        missing_count = self.df[col].isnull().sum()
        if missing_count == 0:
            logger.info(f"{col}: 欠損値なし")
            return
        
        logger.info(f"{col}の欠損値を最頻値で補完中... ({missing_count}個)")
        
        # 最頻値を計算
        mode_value = self.df[col].mode()
        if len(mode_value) > 0:
            self.df[col] = self.df[col].fillna(mode_value[0])
            logger.info(f"{col}: 最頻値 {mode_value[0]} で補完完了")
        else:
            logger.warning(f"{col}: 最頻値が計算できません")
    
    def fill_with_forward_fill(self, col, limit=7):
        """前方補完で欠損値を補完（週先データ使用）"""
        if col not in self.df.columns:
            logger.warning(f"列 '{col}' が存在しません")
            return
        
        missing_count = self.df[col].isnull().sum()
        if missing_count == 0:
            logger.info(f"{col}: 欠損値なし")
            return
        
        logger.info(f"{col}の欠損値を前方補完で補完中... ({missing_count}個, limit={limit})")
        
        # 前方補完（制限付き）
        self.df[col] = self.df[col].ffill(limit=limit)
        
        remaining_missing = self.df[col].isnull().sum()
        logger.info(f"{col}: 前方補完完了 (残存欠損値: {remaining_missing})")
    
    def calculate_humidex(self):
        """体感温度（Humidex）の計算"""
        logger.info("体感温度（Humidex）を計算中...")
        
        def calc_humidex_value(row):
            """単一行の体感温度計算"""
            if pd.isna(row['temperature']) or pd.isna(row['dew_point']):
                return None
            
            T = row['temperature']
            DP = row['dew_point']
            
            # Humidex計算式
            return round(T + (0.5555 * (6.11 * math.exp(5417.7530 * (1/273.15 - 1/(DP + 273.15))) - 10)), 2)
        
        # 既存のhumidex_v列があるかチェック
        if 'humidex_v' in self.df.columns:
            logger.info("既存のhumidex_v列を上書きします")
        
        # Humidex計算
        self.df['humidex_v'] = self.df.apply(calc_humidex_value, axis=1)
        
        calculated_count = self.df['humidex_v'].notna().sum()
        logger.info(f"Humidex計算完了: {calculated_count}行で計算成功")
    
    def clean_data(self):
        """データクリーニングの実行"""
        logger.info("=== データクリーニング開始 ===")
        
        # 1. 不要列の削除
        self.remove_unnecessary_columns()
        
        # 2. 欠損値分析
        self.analyze_missing_values()
        
        # 3. 各列の欠損値補完
        logger.info("欠損値補完開始...")
        
        # 風向（円形統計）
        self.fill_wind_direction_circular('wind_dir_10s')
        
        # 視程（線形補間）
        self.fill_visibility_interpolation('visibility')
        
        # 雲量（最頻値）
        self.fill_cloud_cover_mode('cloud_cover_8')
        
        # 相対湿度（前方補完）
        self.fill_with_forward_fill('relative_humidity', limit=7)
        
        # 露点温度（前方補完）
        self.fill_with_forward_fill('dew_point', limit=7)
        
        # 4. Humidex計算
        self.calculate_humidex()
        
        # 5. 最終的な欠損値数を記録
        self.final_missing_count = self.df.isnull().sum().sum()
        
        logger.info("=== データクリーニング完了 ===")
        logger.info(f"欠損値数: {self.original_missing_count} → {self.final_missing_count}")
    
    def show_cleaning_summary(self):
        """クリーニング結果のサマリー表示"""
        logger.info("=== クリーニング結果サマリー ===")
        
        # 補完例の表示
        key_columns = ['wind_dir_10s', 'visibility', 'cloud_cover_8']
        
        for col in key_columns:
            if col in self.df.columns:
                filled_count = self.df[col].notna().sum()
                logger.info(f"{col}: {filled_count}行のデータ")
        
        # データ統計
        logger.info(f"最終データ形状: {self.df.shape}")
        logger.info(f"最終欠損値数: {self.final_missing_count}")
        logger.info(f"データ期間: {self.df['date_time_local'].min()} ～ {self.df['date_time_local'].max()}" 
                   if 'date_time_local' in self.df.columns else "日時列なし")
    
    def save_data(self):
        """クリーニング済みデータの保存"""
        try:
            logger.info(f"クリーニング済みデータを保存中: {self.output_file}")
            self.df.to_csv(self.output_file, index=False)
            logger.info(f"保存完了: {self.output_file}")
            
            # ファイルサイズ確認
            file_size = self.output_file.stat().st_size
            logger.info(f"出力ファイルサイズ: {file_size:,} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"データ保存エラー: {e}")
            return False
    
    def run(self):
        """メイン処理の実行"""
        logger.info("=== Climate Data Cleaner 開始 ===")
        
        # データ読み込み
        if not self.load_data():
            return False
        
        # データクリーニング
        self.clean_data()
        
        # 結果サマリー
        self.show_cleaning_summary()
        
        # データ保存
        if not self.save_data():
            return False
        
        logger.info("=== Climate Data Cleaner 完了 ===")
        return True


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description="Vancouver Climate Data Cleaner")
    parser.add_argument("input_file", help="入力CSVファイルパス")
    parser.add_argument("-o", "--output", help="出力CSVファイルパス（省略時は自動生成）")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細ログ出力")
    
    args = parser.parse_args()
    
    # ログレベル設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 入力ファイル存在確認
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"入力ファイルが存在しません: {input_path}")
        return 1
    
    # クリーニング実行
    cleaner = ClimateDataCleaner(args.input_file, args.output)
    
    if cleaner.run():
        logger.info("処理が正常に完了しました")
        return 0
    else:
        logger.error("処理中にエラーが発生しました")
        return 1


if __name__ == "__main__":
    exit(main())