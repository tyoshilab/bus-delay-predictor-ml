"""
モデル構築・訓練モジュール
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from keras import layers
from keras.models import Model
from keras.optimizers import Adam
import warnings
warnings.filterwarnings('ignore')

class DelayPredictionModel:
    """遅延予測モデルクラス"""
    
    def __init__(self, input_timesteps=8, output_timesteps=3):
        """
        Args:
            input_timesteps (int): 入力時系列長
            output_timesteps (int): 出力時系列長
        """
        self.input_timesteps = input_timesteps
        self.output_timesteps = output_timesteps
        self.model = None
        self.history = None
    
    def create_delay_prediction_convlstm_model(self, input_shape):
        """
        遅延予測用双方向ConvLSTMモデルを作成
        
        Args:
            input_shape (tuple): 入力形状 (timesteps, height, width, channels)
            
        Returns:
            tf.keras.Model: 構築されたモデル
        """
        actual_feature_count = input_shape[2]  # width from input_shape
        
        # 入力層
        inputs = layers.Input(shape=input_shape)
        
        # エンコーダ部分
        # 1層目: ConvLSTM2D + Bidirectional
        encoder_1 = layers.Bidirectional(
            layers.ConvLSTM2D(
                filters=64,
                kernel_size=(1, actual_feature_count),
                strides=(1, actual_feature_count),
                activation='linear',
                return_sequences=True,
                return_state=False,
                dropout=0.2
            )
        )(inputs)
        
        encoder_1 = layers.BatchNormalization()(encoder_1)
        encoder_1 = layers.Dropout(0.1)(encoder_1)
        
        # 2層目: ConvLSTM2D + Bidirectional
        encoder_2 = layers.Bidirectional(
            layers.ConvLSTM2D(
                filters=32,
                kernel_size=(1, 1),
                activation='linear',
                return_sequences=False,  # 最後のタイムステップのみ
                dropout=0.1
            )
        )(encoder_1)
        
        encoder_2 = layers.BatchNormalization()(encoder_2)
        encoder_2 = layers.Dropout(0.1)(encoder_2)
        
        # Flatten層
        flattened = layers.Flatten()(encoder_2)
        
        # デコーダ部分
        # RepeatVector
        repeated = layers.RepeatVector(self.output_timesteps)(flattened)
        
        # Reshape for ConvLSTM2D
        reshaped = layers.Reshape((self.output_timesteps, 1, 1, flattened.shape[-1]))(repeated)
        
        # デコーダ1層目
        decoder_1 = layers.Bidirectional(
            layers.ConvLSTM2D(
                filters=32,
                kernel_size=(1, 1),
                activation='linear',
                return_sequences=True,
                dropout=0.1
            )
        )(reshaped)
        
        decoder_1 = layers.BatchNormalization()(decoder_1)
        decoder_1 = layers.Dropout(0.1)(decoder_1)
        
        # デコーダ2層目
        decoder_2 = layers.Bidirectional(
            layers.ConvLSTM2D(
                filters=16,
                kernel_size=(1, 1),
                activation='linear',
                return_sequences=True,
                dropout=0.1
            )
        )(decoder_1)
        
        decoder_2 = layers.BatchNormalization()(decoder_2)
        
        # TimeDistributed出力層（遅延時間予測：線形活性化）
        outputs = layers.TimeDistributed(
            layers.Dense(1, activation='linear')  # 遅延は正負両方の値を取るため線形
        )(decoder_2)
        
        # 最終的な形状調整
        outputs = layers.Reshape((self.output_timesteps,))(outputs)
        
        model = Model(inputs=inputs, outputs=outputs)
        
        return model
    
    def create_delay_evaluation_metrics(self):
        """遅延予測専用の評価指標を作成"""
        
        def delay_mae(y_true, y_pred):
            """遅延予測用MAE"""
            # Multi-timestepの場合は全体の平均を計算
            return tf.reduce_mean(tf.abs(y_true - y_pred))
        
        def delay_rmse(y_true, y_pred):
            """遅延予測用RMSE"""
            # Multi-timestepの場合は全体の平均を計算
            mse = tf.reduce_mean(tf.square(y_true - y_pred))
            return tf.sqrt(mse)
        
        def delay_mape_safe(y_true, y_pred):
            """遅延時間用MAPE（ゼロ除算対策付き）"""
            epsilon = 1e-8
            # 遅延は正負両方の値を取るため、絶対値で計算
            y_true_abs = tf.abs(y_true)
            percentage_error = tf.abs(y_true - y_pred) / tf.maximum(y_true_abs, epsilon)
            return tf.reduce_mean(percentage_error) * 100
        
        def delay_direction_accuracy(y_true, y_pred):
            """遅延方向精度（早い/遅いの方向予測精度）"""
            # Multi-timestepの場合は最後のタイムステップを使用
            if len(y_true.shape) > 1 and y_true.shape[-1] > 1:
                y_true_final = y_true[:, -1]  # 最後のタイムステップ
            else:
                y_true_final = y_true
                
            if len(y_pred.shape) > 1 and y_pred.shape[-1] > 1:
                y_pred_final = y_pred[:, -1]  # 最後のタイムステップ
            else:
                y_pred_final = y_pred
                
            true_sign = tf.sign(y_true_final)
            pred_sign = tf.sign(y_pred_final)
            return tf.reduce_mean(tf.cast(tf.equal(true_sign, pred_sign), tf.float32))
        
        def on_time_prediction_accuracy(y_true, y_pred):
            """定時予測精度（閾値以内の予測精度）"""
            # Multi-timestepの場合は最後のタイムステップを使用
            if len(y_true.shape) > 1 and y_true.shape[-1] > 1:
                y_true_final = y_true[:, -1]
            else:
                y_true_final = y_true
                
            if len(y_pred.shape) > 1 and y_pred.shape[-1] > 1:
                y_pred_final = y_pred[:, -1]
            else:
                y_pred_final = y_pred
                
            threshold = 60.0  # 1分以内を定時とする
            true_on_time = tf.abs(y_true_final) <= threshold
            pred_on_time = tf.abs(y_pred_final) <= threshold
            return tf.reduce_mean(tf.cast(tf.equal(true_on_time, pred_on_time), tf.float32))
        
        return {
            'delay_mae': delay_mae,
            'delay_rmse': delay_rmse,
            'delay_mape_safe': delay_mape_safe,
            'delay_direction_accuracy': delay_direction_accuracy,
            'on_time_prediction_accuracy': on_time_prediction_accuracy
        }
    
    def build_model(self, input_shape):
        """モデルを構築・コンパイル"""
        print("=== Delay Prediction ConvLSTM Model ===")
        
        # モデル作成
        self.model = self.create_delay_prediction_convlstm_model(input_shape)
        
        # 評価指標の準備
        evaluation_metrics = self.create_delay_evaluation_metrics()
        
        # モデルコンパイル
        self.model.compile(
            optimizer=Adam(
                learning_rate=0.001,
                beta_1=0.9,
                beta_2=0.999,
                epsilon=1e-7
            ),
            loss='mse',  # 遅延予測には平均二乗誤差が適している
            metrics=[
                'mae',  # 平均絶対誤差
                evaluation_metrics['delay_rmse'],  # RMSE
                evaluation_metrics['delay_direction_accuracy'],  # 方向精度
                evaluation_metrics['on_time_prediction_accuracy']  # 定時予測精度
            ]
        )
        
        # モデル概要表示
        self.model.summary()
        
        print(f"\n=== Model Details ===")
        print(f"Input shape: {self.model.input.shape}")
        print(f"Output shape: {self.model.output.shape}")
        print(f"Total parameters: {self.model.count_params():,}")
        
        return self.model
    
    def create_callbacks(self, model_path='best_delay_model.h5'):
        """訓練用コールバックを作成"""
        early_stopping = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=15,
            restore_best_weights=True,
            verbose=1
        )
        
        reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.7,
            patience=7,
            min_lr=1e-6,
            verbose=1
        )
        
        model_checkpoint = tf.keras.callbacks.ModelCheckpoint(
            model_path,
            monitor='val_loss',
            save_best_only=True,
            save_weights_only=False,
            verbose=1
        )
        
        return [early_stopping, reduce_lr, model_checkpoint]
    
    def train_model(self, X_train, y_train, batch_size=32, epochs=50, validation_split=0.2, 
                   model_path='best_delay_model.h5'):
        """
        モデルを訓練
        
        Args:
            X_train (np.array): 訓練入力データ
            y_train (np.array): 訓練目標データ
            batch_size (int): バッチサイズ
            epochs (int): エポック数
            validation_split (float): 検証データ分割率
            model_path (str): モデル保存パス
            
        Returns:
            tf.keras.History: 訓練履歴
        """
        if self.model is None:
            raise ValueError("Model must be built before training. Call build_model() first.")
        
        print(f"\n=== Training Configuration ===")
        print(f"Batch size: {batch_size}")
        print(f"Maximum epochs: {epochs}")
        print(f"Validation split: {validation_split}")
        
        # コールバック作成
        callbacks_list = self.create_callbacks(model_path)
        
        # データタイプを明示的にfloat32に変換
        X_train_fixed = X_train.astype(np.float32)
        y_train_fixed = y_train.astype(np.float32)
        
        # バッチサイズの調整（エラー回避）
        batch_size_safe = min(batch_size, len(X_train_fixed) // 10)
        
        print(f"\n=== Training Execution ===")
        print(f"Training data shape: {X_train_fixed.shape}")
        print(f"Target data shape: {y_train_fixed.shape}")
        print(f"Adjusted batch size: {batch_size_safe}")
        
        try:
            import time
            start_time = time.time()
            
            # 訓練実行
            self.history = self.model.fit(
                X_train_fixed,
                y_train_fixed,
                batch_size=batch_size_safe,
                epochs=epochs,
                validation_split=validation_split,
                callbacks=callbacks_list,
                verbose=1,
                shuffle=True
            )
            
            training_time = time.time() - start_time
            print(f"\n=== Training Complete ===")
            print(f"Training time: {training_time/60:.2f} minutes")
            print(f"Total epochs: {len(self.history.history['loss'])}")
            print(f"Best val_loss: {min(self.history.history['val_loss']):.6f}")
            
            # 訓練履歴の表示
            final_metrics = {
                'loss': self.history.history['loss'][-1],
                'val_loss': self.history.history['val_loss'][-1],
                'mae': self.history.history['mae'][-1],
                'val_mae': self.history.history['val_mae'][-1]
            }
            
            print(f"\n=== Final Metrics ===")
            for metric, value in final_metrics.items():
                print(f"{metric}: {value:.6f}")
            
            return self.history
                
        except Exception as e:
            print(f"Error occurred during training: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            
            # 小さなサンプルでテスト
            print(f"\nSmall sample test:")
            try:
                small_X = X_train_fixed[:2]  # 最初の2サンプル
                small_y = y_train_fixed[:2]
                test_prediction = self.model.predict(small_X, verbose=0)
                print(f"  Small sample prediction success: input{small_X.shape} -> output{test_prediction.shape}")
            except Exception as small_e:
                print(f"  Small sample prediction failed: {str(small_e)}")
            
            return None
    
    def predict(self, X_test, batch_size=32):
        """予測実行"""
        if self.model is None:
            raise ValueError("Model must be built and trained before prediction.")
        
        X_test_fixed = X_test.astype(np.float32)
        predictions = self.model.predict(X_test_fixed, batch_size=batch_size, verbose=1)
        return predictions
    
    def save_model(self, filepath):
        """モデル保存"""
        if self.model is not None:
            self.model.save(filepath)
            print(f"Model saved to {filepath}")
    
    def load_model(self, filepath):
        """モデル読み込み"""
        self.model = tf.keras.models.load_model(filepath)
        print(f"Model loaded from {filepath}")

def main():
    """メイン関数 - テスト用"""
    print("Model building and training module loaded successfully")

if __name__ == "__main__":
    main()
