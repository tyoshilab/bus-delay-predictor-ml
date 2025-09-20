"""
データ標準化クラス
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class DataStandardizer:
    """データ標準化クラス"""
    
    def __init__(self):
        """初期化"""
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        
    def fit_scalers(self, X_train, y_train):
        """
        標準化パラメータを学習
        
        Args:
            X_train (np.array): 訓練用入力データ
            y_train (np.array): 訓練用目標データ
        """
        # 入力データ用スケーラー（3D -> 2D -> fit）
        X_train_2d = X_train.reshape(-1, X_train.shape[-1])
        self.feature_scaler.fit(X_train_2d)
        
        # 目標データ用スケーラー
        self.target_scaler.fit(y_train.reshape(-1, 1))
        
    def transform_features(self, X):
        """
        入力データの標準化
        
        Args:
            X (np.array): 入力データ
            
        Returns:
            np.array: 標準化済み入力データ
        """
        original_shape = X.shape
        X_2d = X.reshape(-1, X.shape[-1])
        X_scaled = self.feature_scaler.transform(X_2d)
        return X_scaled.reshape(original_shape)
        
    def transform_targets(self, y):
        """
        目標データの標準化
        
        Args:
            y (np.array): 目標データ
            
        Returns:
            np.array: 標準化済み目標データ
        """
        return self.target_scaler.transform(y.reshape(-1, 1)).flatten()
        
    def inverse_transform_targets(self, y_scaled):
        """
        目標データの逆標準化
        
        Args:
            y_scaled (np.array): 標準化済み目標データ
            
        Returns:
            np.array: 元のスケールの目標データ
        """
        return self.target_scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()
    
    def fit_transform_features(self, X):
        """
        入力データの学習と標準化を同時実行
        
        Args:
            X (np.array): 入力データ
            
        Returns:
            np.array: 標準化済み入力データ
        """
        original_shape = X.shape
        X_2d = X.reshape(-1, X.shape[-1])
        X_scaled = self.feature_scaler.fit_transform(X_2d)
        return X_scaled.reshape(original_shape)
        
    def fit_transform_targets(self, y):
        """
        目標データの学習と標準化を同時実行
        
        Args:
            y (np.array): 目標データ
            
        Returns:
            np.array: 標準化済み目標データ
        """
        return self.target_scaler.fit_transform(y.reshape(-1, 1)).flatten()
