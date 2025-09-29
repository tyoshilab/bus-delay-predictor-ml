#!/usr/bin/env python3
"""
Climate Data Cleaner - Usage Examples and Test Script
"""

import subprocess
import sys
from pathlib import Path
import pandas as pd

def run_cleaner_example():
    """クリーナーの実行例"""
    print("=== Climate Data Cleaner 使用例 ===")
    
    # 使用可能なCSVファイルを探す
    climate_dir = Path("/workspace/GTFS/climate")
    csv_files = list(climate_dir.glob("weatherstats_vancouver_hourly*.csv"))
    
    if not csv_files:
        print("❌ weatherstats_vancouver_hourly*.csv ファイルが見つかりません")
        print("最初にスクレイピングまたは手動でCSVファイルを配置してください")
        return False
    
    # 最初に見つかったファイルを使用
    input_file = csv_files[0]
    print(f"📁 入力ファイル: {input_file}")
    
    # クリーナー実行
    cleaner_script = climate_dir / "clean_climate_data.py"
    
    try:
        print("🚀 クリーニング実行中...")
        result = subprocess.run([
            sys.executable, str(cleaner_script), 
            str(input_file), 
            "-v"  # 詳細ログ
        ], capture_output=True, text=True, cwd=str(climate_dir))
        
        if result.returncode == 0:
            print("✅ クリーニング成功")
            print("📤 出力:")
            print(result.stdout)
            
            # 出力ファイルの確認
            output_file = input_file.parent / (input_file.stem + "_filled.csv")
            if output_file.exists():
                print(f"📁 出力ファイル: {output_file}")
                
                # 簡単な統計表示
                try:
                    df = pd.read_csv(output_file)
                    print(f"📊 出力データ統計:")
                    print(f"  - 行数: {len(df):,}")
                    print(f"  - 列数: {len(df.columns)}")
                    print(f"  - 欠損値数: {df.isnull().sum().sum()}")
                    print(f"  - データサイズ: {output_file.stat().st_size:,} bytes")
                except Exception as e:
                    print(f"⚠️  統計計算エラー: {e}")
            
            return True
        else:
            print("❌ クリーニング失敗")
            print("エラー出力:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        return False

def show_usage_examples():
    """使用方法の説明"""
    print("""
=== Climate Data Cleaner 使用方法 ===

1. 基本的な使用方法:
   python clean_climate_data.py input.csv

2. 出力ファイル指定:
   python clean_climate_data.py input.csv -o output_clean.csv

3. 詳細ログ付き実行:
   python clean_climate_data.py input.csv -v

4. 実際の例:
   python clean_climate_data.py weatherstats_vancouver_hourly.csv
   → weatherstats_vancouver_hourly_filled.csv が生成される

=== 処理内容 ===
✓ 不要列の削除 (wind_dir, wind_gust, windchill等)
✓ 風向の円形統計による補完
✓ 視程の線形補間による補完  
✓ 雲量の最頻値による補完
✓ 相対湿度・露点の前方補完
✓ 体感温度(Humidex)の計算

=== 出力 ===
- 欠損値が適切に補完されたCSVファイル
- 詳細なクリーニングログ
- 処理前後の統計比較
""")

def test_with_sample_data():
    """サンプルデータでのテスト"""
    print("=== サンプルデータテスト ===")
    
    # サンプルデータ作成
    sample_file = Path("/workspace/GTFS/climate/sample_weather.csv")
    
    # 欠損値を含むサンプルデータ
    sample_data = {
        'date_time_local': ['2025-01-01 10:00:00', '2025-01-01 11:00:00', '2025-01-01 12:00:00'],
        'temperature': [15.5, 16.2, 17.0],
        'relative_humidity': [65.0, None, 70.0],
        'dew_point': [8.5, None, 10.2],
        'wind_dir_10s': [180.0, None, 200.0],
        'visibility': [15000, None, 12000],
        'cloud_cover_8': [4, None, 6],
        'pressure_sea': [1013.2, 1013.5, 1013.8],
        'wind_speed': [5.2, 6.1, 4.8],
        'humidex': [None, None, None]  # 計算されるべき列
    }
    
    try:
        df = pd.DataFrame(sample_data)
        df.to_csv(sample_file, index=False)
        print(f"📁 サンプルファイル作成: {sample_file}")
        
        # クリーニング実行
        cleaner_script = Path("/workspace/GTFS/climate/clean_climate_data.py")
        result = subprocess.run([
            sys.executable, str(cleaner_script), 
            str(sample_file), 
            "-v"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ サンプルデータクリーニング成功")
            
            # 結果確認
            output_file = sample_file.parent / (sample_file.stem + "_filled.csv")
            if output_file.exists():
                df_cleaned = pd.read_csv(output_file)
                print("📊 クリーニング結果:")
                print(df_cleaned)
                
                # サンプルファイル削除
                sample_file.unlink()
                output_file.unlink()
                print("🧹 サンプルファイル削除完了")
        else:
            print("❌ サンプルデータクリーニング失敗")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ サンプルテストエラー: {e}")

def main():
    """メイン実行"""
    print("Climate Data Cleaner - Test & Example Script")
    print("=" * 50)
    
    # 使用方法表示
    show_usage_examples()
    
    # サンプルデータテスト
    test_with_sample_data()
    
    # 実際のファイルでの実行例
    if input("\n実際のファイルでクリーニングを実行しますか? (y/N): ").lower() == 'y':
        run_cleaner_example()

if __name__ == "__main__":
    main()