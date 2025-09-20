# GTFS Bus Delay Prediction - Data Management Framework

このプロジェクトは、バンクーバーのGTFSデータを使用したバス遅延予測モデルのデータ管理プロセスを、再利用可能なPythonモジュールに分離した構成になっています。

## 🗂️ ディレクトリ構造

```
GTFS/
├── src/                              # カスタムモジュール
│   ├── __init__.py                   # パッケージ初期化
│   ├── data_connection.py            # データベース接続・データ取得
│   ├── data_preprocessing.py         # データ前処理・特徴量エンジニアリング
│   ├── timeseries_processing.py      # 時系列データ作成・データ分割
│   ├── model_training.py             # モデル構築・訓練
│   ├── evaluation.py                 # 評価・可視化
│   └── main_pipeline.py              # メインパイプライン
├── bus_arrival_forecast_model.ipynb  # 元のnotebook（モジュール参照版）
└── README.md                         # このファイル
```

## 📋 データ管理プロセス

### 1. データベース接続・データ取得 (`data_connection.py`)
- **DatabaseConnector**: PostgreSQLデータベースへの接続管理
- **GTFSDataRetriever**: GTFSリアルタイムデータの取得・前処理
- **WeatherDataRetriever**: 気象データの取得・前処理

### 2. データ前処理・特徴量エンジニアリング (`data_preprocessing.py`)
- **DataPreprocessor**: 欠損値処理、外れ値除去、高度な特徴量生成
- **DataAggregator**: 時間バケット集約、データ品質向上
- **FeatureEngineer**: 特徴量結合、動的特徴量選択

### 3. 時系列データ作成・データ分割 (`timeseries_processing.py`)
- **SequenceCreator**: route_id + direction_id別の時系列シーケンス作成
- **DataSplitter**: 時間順データ分割、ConvLSTM用reshape
- **DataStandardizer**: 選択的特徴量標準化、スケーラー管理

### 4. モデル構築・訓練 (`model_training.py`)
- **DelayPredictionModel**: 双方向ConvLSTMモデル、評価指標、訓練管理

### 5. 評価・可視化 (`evaluation.py`)
- **ModelEvaluator**: 遅延予測専用評価指標、レベル別分析
- **ModelVisualizer**: 予測結果可視化、訓練履歴可視化

## 🚀 使用方法

### 基本的な使用法

```python
# カスタムモジュールのインポート
from src.data_connection import DatabaseConnector, GTFSDataRetriever, WeatherDataRetriever
from src.data_preprocessing import DataPreprocessor, DataAggregator, FeatureEngineer
from src.timeseries_processing import SequenceCreator, DataSplitter, DataStandardizer
from src.model_training import DelayPredictionModel
from src.evaluation import ModelEvaluator, ModelVisualizer

# 1. データ取得
db_connector = DatabaseConnector()
gtfs_retriever = GTFSDataRetriever(db_connector)
weather_retriever = WeatherDataRetriever(db_connector)

gtfs_data = gtfs_retriever.get_gtfs_data(route_id='6612')
weather_data = weather_retriever.get_weather_data()

# 2. データ前処理
preprocessor = DataPreprocessor()
filtered_data = preprocessor.sophisticated_preprocessing(gtfs_data)

aggregator = DataAggregator()
delay_aggregated = aggregator.create_optimized_time_buckets(filtered_data)
weather_aggregated = aggregator.create_weather_aggregation(weather_data)

feature_engineer = FeatureEngineer()
delay_features = feature_engineer.merge_features(delay_aggregated, weather_aggregated)

# 3. 時系列データ作成
sequence_creator = SequenceCreator(input_timesteps=8, output_timesteps=3)
X, y, _, used_features = sequence_creator.create_route_direction_aware_sequences(
    delay_features, 'arrival_delay', feature_cols
)

# 4. データ分割・標準化
data_splitter = DataSplitter()
X_train, X_test, y_train, y_test = data_splitter.train_test_split_temporal(X, y)

standardizer = DataStandardizer()
X_train_scaled, X_test_scaled, y_train_scaled, y_test_scaled = standardizer.standardize_data(
    X_train, X_test, y_train, y_test, used_features
)

# 5. モデル訓練
model_trainer = DelayPredictionModel()
model = model_trainer.build_model(input_shape)
history = model_trainer.train_model(X_train_scaled, y_train_scaled)

# 6. 評価・可視化
predictions = model_trainer.predict(X_test_scaled)
evaluator = ModelEvaluator()
visualizer = ModelVisualizer()

metrics = evaluator.calculate_delay_metrics(y_test, predictions)
visualizer.plot_prediction_analysis(y_test, predictions, metrics)
```

### ワンライン実行

```python
# メインパイプラインの実行
from src.main_pipeline import main
main()
```

### Notebookでの使用

元のnotebook (`bus_arrival_forecast_model.ipynb`) は、カスタムモジュールを参照する形式に更新されています。各セルでプロセスごとに分離されたモジュールを使用できます。

## 🔧 モジュールの特徴

### 再利用性
- 各プロセスが独立したクラスとして実装
- パラメータ化された設定
- 異なるデータセットへの適用が容易

### 拡張性
- 新しい特徴量エンジニアリング手法の追加が簡単
- 異なるモデルアーキテクチャへの対応
- 評価指標のカスタマイズ

### 保守性
- 明確な責務分離
- エラーハンドリング
- ログ出力とデバッグ支援

## 💻 動作環境

- Python 3.8+
- TensorFlow 2.x
- pandas, numpy, scikit-learn
- matplotlib, seaborn
- psycopg2

## 📊 期待される結果

このフレームワークを使用することで、以下のような遅延予測性能が期待できます：

- **MAE**: 1-2分程度
- **方向予測精度**: 70-80%
- **1分以内精度**: 40-60%
- **R²スコア**: 0.3-0.5

## 🔄 今後の拡張

1. **多路線対応**: 複数路線の同時学習
2. **リアルタイム予測**: ストリーミングデータ対応
3. **アンサンブル手法**: 複数モデルの組み合わせ
4. **外部要因**: イベント、工事情報の組み込み

---

**Author**: GTFS Analysis Team  
**Version**: 1.0.0  
**Last Updated**: 2025年9月9日
