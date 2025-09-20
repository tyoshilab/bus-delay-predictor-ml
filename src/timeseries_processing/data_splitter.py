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
