"""
モデル可視化クラス
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

class ModelVisualizer:
    """モデル可視化クラス"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def plot_prediction_analysis(self, y_true, y_pred, overall_metrics):
        """予測分析の可視化"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 予測値 vs 実際値
        axes[0, 0].scatter(y_true, y_pred, alpha=0.5, s=1)
        axes[0, 0].plot([y_true.min(), y_true.max()], 
                        [y_true.min(), y_true.max()], 'r--', lw=2)
        axes[0, 0].set_xlabel('Actual Delay Time (seconds)')
        axes[0, 0].set_ylabel('Predicted Delay Time (seconds)')
        axes[0, 0].set_title(f'Predicted vs Actual Values (R² = {overall_metrics["r2"]:.3f})')
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 誤差分布
        residuals = y_true - y_pred
        axes[0, 1].hist(residuals, bins=50, alpha=0.7, edgecolor='black')
        axes[0, 1].set_xlabel('Prediction Error (seconds)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title(f'Prediction Error Distribution (MAE = {overall_metrics["mae"]:.1f}s)')
        axes[0, 1].axvline(0, color='red', linestyle='--', alpha=0.7)
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 絶対誤差の分布
        axes[1, 0].hist(overall_metrics['abs_errors'], bins=50, alpha=0.7, edgecolor='black')
        axes[1, 0].set_xlabel('Absolute Error (seconds)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].set_title('Absolute Error Distribution')
        # 範囲別の閾値を表示
        for range_name, threshold in [('1min', 60), ('2min', 120), ('5min', 300)]:
            axes[1, 0].axvline(threshold, color='red', linestyle='--', alpha=0.7, 
                              label=f'{range_name}')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        # 4. 時系列予測の例（単一予測点の場合はメッセージ表示）
        axes[1, 1].text(0.5, 0.5, 'Single time point prediction\nNo time series display', 
                       ha='center', va='center', transform=axes[1, 1].transAxes)
        axes[1, 1].set_title('Time Series Prediction')

        plt.tight_layout()
        plt.show()
    
    def plot_delay_level_analysis(self, y_true, y_pred, delay_level_analysis):
        """遅延レベル別分析の可視化"""
        
        # 遅延レベル別の可視化
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # 1. 遅延レベル別分布
        level_names = list(delay_level_analysis.keys())
        level_counts = [delay_level_analysis[name]['count'] for name in level_names]
        level_percentages = [delay_level_analysis[name]['percentage'] for name in level_names]

        axes[0, 0].bar(level_names, level_counts)
        axes[0, 0].set_title('Sample Count by Delay Level')
        axes[0, 0].set_ylabel('Sample Count')
        axes[0, 0].tick_params(axis='x', rotation=45)

        # パーセンテージを追加表示
        for i, (count, pct) in enumerate(zip(level_counts, level_percentages)):
            if count > 0:
                axes[0, 0].text(i, count + max(level_counts)*0.01, f'{pct:.1f}%', 
                                ha='center', va='bottom')

        # 2. 遅延レベル別MAE
        level_maes = [delay_level_analysis[name]['mae'] for name in level_names]
        axes[0, 1].bar(level_names, level_maes)
        axes[0, 1].set_title('Mean Absolute Error by Delay Level')
        axes[0, 1].set_ylabel('MAE (seconds)')
        axes[0, 1].tick_params(axis='x', rotation=45)

        # 3. 遅延レベル別方向精度
        level_dir_acc = [delay_level_analysis[name]['direction_accuracy'] for name in level_names]
        axes[1, 0].bar(level_names, level_dir_acc)
        axes[1, 0].set_title('Direction Prediction Accuracy by Delay Level')
        axes[1, 0].set_ylabel('Accuracy')
        axes[1, 0].set_ylim(0, 1)
        axes[1, 0].tick_params(axis='x', rotation=45)

        # 4. 実際値vs予測値（レベル別色分け）
        delay_levels = {
            'Very Early': (-float('inf'), -120),
            'Early': (-120, -30),
            'On Time': (-30, 30),
            'Minor Delay': (30, 300),
            'Major Delay': (300, float('inf'))
        }

        sample_levels = []
        for true_val in y_true:
            for level_name, (min_delay, max_delay) in delay_levels.items():
                if max_delay == float('inf'):
                    if true_val >= min_delay:
                        sample_levels.append(level_name)
                        break
                elif min_delay == -float('inf'):
                    if true_val < max_delay:
                        sample_levels.append(level_name)
                        break
                else:
                    if min_delay <= true_val < max_delay:
                        sample_levels.append(level_name)
                        break

        # レベル別色分けプロット
        colors = ['red', 'orange', 'green', 'blue', 'purple']
        level_colors = dict(zip(['Very Early', 'Early', 'On Time', 'Minor Delay', 'Major Delay'], colors))

        for level_name in level_colors.keys():
            mask = np.array(sample_levels) == level_name
            if np.sum(mask) > 0:
                axes[1, 1].scatter(y_true[mask], y_pred[mask], 
                                  c=level_colors[level_name], label=level_name, alpha=0.6, s=2)

        axes[1, 1].plot([y_true.min(), y_true.max()], 
                        [y_true.min(), y_true.max()], 'k--', lw=1)
        axes[1, 1].set_xlabel('Actual Delay Time (seconds)')
        axes[1, 1].set_ylabel('Predicted Delay Time (seconds)')
        axes[1, 1].set_title('Prediction Accuracy by Delay Level')
        axes[1, 1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()
    
    def plot_training_history(self, history):
        """訓練履歴の可視化"""
        if history is None:
            print("No training history available")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Loss
        axes[0, 0].plot(history.history['loss'], label='Training Loss')
        if 'val_loss' in history.history:
            axes[0, 0].plot(history.history['val_loss'], label='Validation Loss')
        axes[0, 0].set_title('Model Loss')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # MAE
        axes[0, 1].plot(history.history['mae'], label='Training MAE')
        if 'val_mae' in history.history:
            axes[0, 1].plot(history.history['val_mae'], label='Validation MAE')
        axes[0, 1].set_title('Mean Absolute Error')
        axes[0, 1].set_ylabel('MAE')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Learning Rate (if available)
        if 'lr' in history.history:
            axes[1, 0].plot(history.history['lr'])
            axes[1, 0].set_title('Learning Rate')
            axes[1, 0].set_ylabel('Learning Rate')
            axes[1, 0].set_xlabel('Epoch')
            axes[1, 0].set_yscale('log')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, 'Learning Rate\nNot Available', 
                           ha='center', va='center', transform=axes[1, 0].transAxes)
        
        # Training metrics summary
        final_epoch = len(history.history['loss'])
        final_loss = history.history['loss'][-1]
        final_val_loss = history.history['val_loss'][-1] if 'val_loss' in history.history else None
        
        summary_text = f"Final Epoch: {final_epoch}\n"
        summary_text += f"Final Training Loss: {final_loss:.6f}\n"
        if final_val_loss:
            summary_text += f"Final Validation Loss: {final_val_loss:.6f}\n"
        summary_text += f"Best Validation Loss: {min(history.history['val_loss']):.6f}" if 'val_loss' in history.history else ""
        
        axes[1, 1].text(0.1, 0.5, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=12, verticalalignment='center')
        axes[1, 1].set_title('Training Summary')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.show()
