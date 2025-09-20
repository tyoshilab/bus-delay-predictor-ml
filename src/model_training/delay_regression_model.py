"""
重回帰による遅延予測モデル
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import warnings
warnings.filterwarnings('ignore')

class DelayRegressionModel:
    """重回帰による遅延予測モデルクラス"""
    
    def __init__(self, model_type='linear', normalize_features=True, feature_names=None):
        """
        Args:
            model_type (str): 使用するモデルタイプ
                - 'linear': 線形回帰
                - 'ridge': Ridge回帰（L2正則化）
                - 'lasso': Lasso回帰（L1正則化）
                - 'elastic': ElasticNet回帰（L1+L2正則化）
                - 'polynomial': 多項式回帰
                - 'random_forest': ランダムフォレスト
                - 'gradient_boosting': 勾配ブースティング
            normalize_features (bool): 特徴量の正規化を行うか
        """
        self.model_type = model_type
        self.normalize_features = normalize_features
        self.model = None
        self.scaler = None
        self.poly_features = None
        self.feature_names = feature_names
        self.training_history = {}
        
    def _create_model(self, **kwargs):
        """指定されたタイプのモデルを作成"""
        if self.model_type == 'linear':
            return LinearRegression(**kwargs)
            
        elif self.model_type == 'ridge':
            return Ridge(alpha=kwargs.get('alpha', 1.0), **kwargs)
            
        elif self.model_type == 'lasso':
            return Lasso(alpha=kwargs.get('alpha', 1.0), max_iter=kwargs.get('max_iter', 1000), **kwargs)
            
        elif self.model_type == 'elastic':
            return ElasticNet(
                alpha=kwargs.get('alpha', 1.0),
                l1_ratio=kwargs.get('l1_ratio', 0.5),
                max_iter=kwargs.get('max_iter', 1000),
                **kwargs
            )
            
        elif self.model_type == 'random_forest':
            return RandomForestRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', None),
                min_samples_split=kwargs.get('min_samples_split', 2),
                min_samples_leaf=kwargs.get('min_samples_leaf', 1),
                random_state=kwargs.get('random_state', 42),
                **kwargs
            )
            
        elif self.model_type == 'gradient_boosting':
            return GradientBoostingRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                learning_rate=kwargs.get('learning_rate', 0.1),
                max_depth=kwargs.get('max_depth', 3),
                random_state=kwargs.get('random_state', 42),
                **kwargs
            )
            
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
    
    def prepare_features(self, X, feature_names=None):
        """特徴量の前処理"""
        if isinstance(X, pd.DataFrame):
            X_array = X.values
            if feature_names is None:
                self.feature_names = X.columns.tolist()
        else:
            X_array = X
            if feature_names is not None:
                self.feature_names = feature_names
            else:
                self.feature_names = [f'feature_{i}' for i in range(X_array.shape[1])]
        
        # 時系列データを平坦化（必要に応じて）
        if len(X_array.shape) > 2:
            original_shape = X_array.shape
            X_array = X_array.reshape(X_array.shape[0], -1)
            print(f"Reshaped input from {original_shape} to {X_array.shape}")
            
            # 特徴量名を更新
            if len(X_array.shape) == 2:
                self.feature_names = [f'feature_{i}' for i in range(X_array.shape[1])]
        
        # 多項式特徴量の生成（polynomial回帰の場合）
        if self.model_type == 'polynomial':
            if self.poly_features is None:
                self.poly_features = PolynomialFeatures(
                    degree=2, 
                    interaction_only=False, 
                    include_bias=False
                )
                X_array = self.poly_features.fit_transform(X_array)
            else:
                X_array = self.poly_features.transform(X_array)
        
        # 特徴量の正規化
        if self.normalize_features:
            if self.scaler is None:
                self.scaler = StandardScaler()
                X_array = self.scaler.fit_transform(X_array)
            else:
                X_array = self.scaler.transform(X_array)
        
        return X_array
    
    def build_model(self, **model_params):
        """モデルを構築"""
        print(f"=== Building {self.model_type.upper()} Regression Model ===")
        
        self.model = self._create_model(**model_params)
        
        print(f"Model type: {self.model_type}")
        print(f"Normalize features: {self.normalize_features}")
        if model_params:
            print(f"Model parameters: {model_params}")
        
        return self.model
    
    def train_model(self, X_train, X_test, y_train, y_test, validation_split=0.2, 
                   perform_cv=True, cv_folds=5, **model_params):
        """
        モデルを訓練
        
        Args:
            X_train: 訓練入力データ
            y_train: 訓練目標データ
            validation_split (float): 検証データ分割率
            perform_cv (bool): クロスバリデーションを実行するか
            cv_folds (int): CVのフォルド数
            **model_params: モデルパラメータ
            
        Returns:
            dict: 訓練結果
        """
        print(f"\n=== Training {self.model_type.upper()} Model ===")
        
        # モデル構築
        if self.model is None:
            self.build_model(**model_params)
        
        # # 特徴量前処理
        # X_processed = self.prepare_features(X_train)
        
        # # 目標変数の形状確認
        # if len(y_train.shape) > 1 and y_train.shape[1] > 1:
        #     print(f"Multi-output target detected: {y_train.shape}")
        #     # 多出力の場合は平均を取る（または最初の出力のみ使用）
        #     y_processed = np.mean(y_train, axis=1) if y_train.shape[1] > 1 else y_train.flatten()
        # else:
        #     y_processed = y_train.flatten()
        
        # print(f"Training data shape: {X_processed.shape}")
        # print(f"Target data shape: {y_processed.shape}")
        # print(f"Feature names: {len(self.feature_names)} features")
        
        # # 訓練・検証データ分割
        # if validation_split > 0:
        #     X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        #         X_processed, y_processed, 
        #         test_size=validation_split, 
        #         random_state=42
        #     )
        # else:
        #     X_train_split, y_train_split = X_processed, y_processed
        #     X_val_split, y_val_split = None, None
        X_processed = np.concatenate((X_train, X_test), axis=0)
        y_processed = np.concatenate((y_train, y_test), axis=0)

        # モデル訓練
        print(f"\nTraining {self.model_type} model...")
        self.model.fit(X_train, y_train)
        
        # 訓練結果の評価
        train_pred = self.model.predict(X_train)
        train_metrics = self._calculate_metrics(y_train, train_pred, "Training")

        # 検証データの評価
        val_metrics = {}
        if validation_split > 0:
            val_pred = self.model.predict(X_test)
            val_metrics = self._calculate_metrics(y_test, val_pred, "Validation")

        # クロスバリデーション
        cv_metrics = {}
        if perform_cv:
            print(f"\nPerforming {cv_folds}-fold cross-validation...")
            cv_scores = cross_val_score(
                self.model, X_processed, y_processed, 
                cv=cv_folds, scoring='neg_mean_squared_error'
            )
            cv_metrics = {
                'cv_mse_mean': -cv_scores.mean(),
                'cv_mse_std': cv_scores.std(),
                'cv_rmse_mean': np.sqrt(-cv_scores.mean()),
                'cv_scores': cv_scores
            }
            print(f"CV RMSE: {cv_metrics['cv_rmse_mean']:.4f} (+/- {cv_metrics['cv_mse_std']:.4f})")
        
        # 特徴量重要度の取得
        feature_importance = self._get_feature_importance()
        
        # 結果をまとめる
        self.training_history = {
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'cv_metrics': cv_metrics,
            'feature_importance': feature_importance,
            'model_type': self.model_type,
            'n_features': X_processed.shape[1],
            'n_samples': X_processed.shape[0]
        }
        
        self._print_training_summary()
        
        return self.training_history
    
    def _calculate_metrics(self, y_true, y_pred, dataset_name):
        """評価指標を計算"""
        metrics = {
            'mse': mean_squared_error(y_true, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred)
        }
        
        # MAPE計算（ゼロ除算対策）
        y_true_abs = np.abs(y_true)
        non_zero_mask = y_true_abs > 1e-8
        if np.any(non_zero_mask):
            mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
            metrics['mape'] = mape
        
        # 方向精度（遅延の正負予測）
        direction_accuracy = np.mean(np.sign(y_true) == np.sign(y_pred))
        metrics['direction_accuracy'] = direction_accuracy
        
        print(f"\n{dataset_name} Metrics:")
        for metric, value in metrics.items():
            print(f"  {metric.upper()}: {value:.4f}")
        
        return metrics
    
    def _get_feature_importance(self):
        """特徴量重要度を取得"""
        if hasattr(self.model, 'feature_importances_'):
            # Tree-based models
            importance = self.model.feature_importances_
        elif hasattr(self.model, 'coef_'):
            # Linear models
            importance = np.abs(self.model.coef_)
        else:
            return None
        
        # 重要度をDataFrameとして整理
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_names[:len(importance)],
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        return feature_importance_df
    
    def _print_training_summary(self):
        """訓練結果のサマリーを表示"""
        print(f"\n=== Training Summary ===")
        print(f"Model: {self.model_type}")
        print(f"Features: {self.training_history['n_features']}")
        print(f"Samples: {self.training_history['n_samples']}")
        
        if self.training_history['cv_metrics']:
            cv_rmse = self.training_history['cv_metrics']['cv_rmse_mean']
            print(f"Cross-validation RMSE: {cv_rmse:.4f}")
        
        # 特徴量重要度トップ10を表示
        if self.training_history['feature_importance'] is not None:
            print(f"\nTop 10 Important Features:")
            top_features = self.training_history['feature_importance'].head(10)
            for _, row in top_features.iterrows():
                print(f"  {row['feature']}: {row['importance']:.4f}")
    
    def predict(self, X_test):
        """予測実行"""
        if self.model is None:
            raise ValueError("Model must be trained before prediction.")
        
        X_processed = self.prepare_features(X_test)
        predictions = self.model.predict(X_processed)
        return predictions
    
    def hyperparameter_tuning(self, X_train, y_train, param_grid=None, cv_folds=5):
        """ハイパーパラメータチューニング"""
        print(f"\n=== Hyperparameter Tuning for {self.model_type} ===")
        
        if param_grid is None:
            param_grid = self._get_default_param_grid()
        
        # 特徴量前処理
        X_processed = self.prepare_features(X_train)
        y_processed = y_train.flatten() if len(y_train.shape) > 1 else y_train
        
        # グリッドサーチ実行
        base_model = self._create_model()
        grid_search = GridSearchCV(
            base_model, param_grid, 
            cv=cv_folds, scoring='neg_mean_squared_error',
            n_jobs=-1, verbose=1
        )
        
        grid_search.fit(X_processed, y_processed)
        
        # 最適なモデルを設定
        self.model = grid_search.best_estimator_
        
        print(f"Best parameters: {grid_search.best_params_}")
        print(f"Best CV score (RMSE): {np.sqrt(-grid_search.best_score_):.4f}")
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
        }
    
    def _get_default_param_grid(self):
        """デフォルトのパラメータグリッドを取得"""
        if self.model_type == 'ridge':
            return {'alpha': [0.1, 1.0, 10.0, 100.0]}
        elif self.model_type == 'lasso':
            return {'alpha': [0.1, 1.0, 10.0, 100.0]}
        elif self.model_type == 'elastic':
            return {
                'alpha': [0.1, 1.0, 10.0],
                'l1_ratio': [0.1, 0.5, 0.9]
            }
        elif self.model_type == 'random_forest':
            return {
                'n_estimators': [50, 100, 200],
                'max_depth': [None, 10, 20],
                'min_samples_split': [2, 5, 10]
            }
        elif self.model_type == 'gradient_boosting':
            return {
                'n_estimators': [50, 100, 200],
                'learning_rate': [0.01, 0.1, 0.2],
                'max_depth': [3, 5, 7]
            }
        else:
            return {}
    
    def save_model(self, filepath):
        """モデル保存"""
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'poly_features': self.poly_features,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'normalize_features': self.normalize_features,
            'training_history': self.training_history
        }
        
        joblib.dump(model_data, filepath)
        print(f"Model saved to {filepath}")
    
    def load_model(self, filepath):
        """モデル読み込み"""
        model_data = joblib.load(filepath)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.poly_features = model_data['poly_features']
        self.feature_names = model_data['feature_names']
        self.model_type = model_data['model_type']
        self.normalize_features = model_data['normalize_features']
        self.training_history = model_data.get('training_history', {})
        
        print(f"Model loaded from {filepath}")
        print(f"Model type: {self.model_type}")
        print(f"Features: {len(self.feature_names) if self.feature_names else 'Unknown'}")

def main():
    """メイン関数 - テスト用"""
    print("Delay Regression Model module loaded successfully")
    
    # サンプルデータでテスト
    print("\n=== Running sample test ===")
    
    # サンプルデータ生成
    np.random.seed(42)
    n_samples = 1000
    n_features = 10
    X_sample = np.random.randn(n_samples, n_features)
    y_sample = (X_sample[:, 0] * 2 + X_sample[:, 1] * -1.5 + 
               X_sample[:, 2] * 0.5 + np.random.randn(n_samples) * 0.1)
    
    # 各種モデルのテスト
    model_types = ['linear', 'ridge', 'random_forest']
    
    for model_type in model_types:
        print(f"\n--- Testing {model_type} model ---")
        model = DelayRegressionModel(model_type=model_type)
        model.train_model(X_sample, y_sample, validation_split=0.2, perform_cv=False)
        
        # 予測テスト
        predictions = model.predict(X_sample[:5])
        print(f"Sample predictions: {predictions}")

if __name__ == "__main__":
    main()