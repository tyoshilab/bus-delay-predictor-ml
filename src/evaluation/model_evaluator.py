"""
モデル評価クラス
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

class ModelEvaluator:
    """モデル評価クラス"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def calculate_delay_metrics(self, y_true, y_pred):
        """遅延予測の詳細評価指標を計算"""
        
        # 基本的な回帰指標
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_true, y_pred)
        
        # 遅延特有の指標
        # 方向精度（早い/遅いの方向が合っているか）
        true_sign = np.sign(y_true)
        pred_sign = np.sign(y_pred)
        direction_accuracy = np.mean(true_sign == pred_sign)
        
        # 定時予測精度（±1分以内）
        threshold = 60  # 秒
        true_ontime = np.abs(y_true) <= threshold
        pred_ontime = np.abs(y_pred) <= threshold
        ontime_accuracy = np.mean(true_ontime == pred_ontime)
        
        # 絶対誤差の分布
        abs_errors = np.abs(y_true - y_pred)
        
        # 範囲別精度
        ranges = {
            'Within 30s': 30,
            'Within 1min': 60,
            'Within 2min': 120,
            'Within 5min': 300
        }
        
        range_accuracies = {}
        for range_name, threshold in ranges.items():
            accurate_predictions = abs_errors <= threshold
            range_accuracies[range_name] = np.mean(accurate_predictions)
        
        return {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'r2': r2,
            'direction_accuracy': direction_accuracy,
            'ontime_accuracy': ontime_accuracy,
            'range_accuracies': range_accuracies,
            'abs_errors': abs_errors
        }
    
    def analyze_by_delay_level(self, y_true, y_pred):
        """遅延レベル別の予測精度を分析"""
        
        # 遅延レベルの定義
        delay_levels = {
            'Very Early': (-float('inf'), -120),  # 2分以上早い
            'Early': (-120, -30),                # 30秒〜2分早い
            'On Time': (-30, 30),                  # ±30秒以内
            'Minor Delay': (30, 300),             # 30秒〜5分遅れ
            'Major Delay': (300, float('inf'))     # 5分以上遅れ
        }
        
        results = {}
        
        for level_name, (min_delay, max_delay) in delay_levels.items():
            # 該当するサンプルを抽出
            if max_delay == float('inf'):
                mask = y_true >= min_delay
            elif min_delay == -float('inf'):
                mask = y_true < max_delay
            else:
                mask = (y_true >= min_delay) & (y_true < max_delay)
            
            if np.sum(mask) > 0:
                level_true = y_true[mask]
                level_pred = y_pred[mask]
                
                # 各レベルでの評価指標
                mae = mean_absolute_error(level_true, level_pred)
                rmse = np.sqrt(mean_squared_error(level_true, level_pred))
                
                # 方向精度
                true_sign = np.sign(level_true)
                pred_sign = np.sign(level_pred)
                direction_acc = np.mean(true_sign == pred_sign)
                
                results[level_name] = {
                    'count': np.sum(mask),
                    'percentage': np.sum(mask) / len(y_true) * 100,
                    'mae': mae,
                    'rmse': rmse,
                    'direction_accuracy': direction_acc,
                    'true_mean': np.mean(level_true),
                    'pred_mean': np.mean(level_pred)
                }
            else:
                results[level_name] = {
                    'count': 0,
                    'percentage': 0,
                    'mae': 0,
                    'rmse': 0,
                    'direction_accuracy': 0,
                    'true_mean': 0,
                    'pred_mean': 0
                }
        
        return results
    
    def evaluation_summary(self, timestep, overall_metrics, delay_level_analysis):
        output = f"""
=== Overall Evaluation Results(time {timestep + 1}h) ===
\nMean Absolute Error (MAE): {overall_metrics['mae']:.3f} seconds
Root Mean Square Error (RMSE): {overall_metrics['rmse']:.3f} seconds
R-squared (R²): {overall_metrics['r2']:.3f}
Direction prediction accuracy: {overall_metrics['direction_accuracy']:.3f}
On-time prediction accuracy: {overall_metrics['ontime_accuracy']:.3f}
\n=== Accuracy by Range ===
        """
        for range_name, accuracy in overall_metrics['range_accuracies'].items():
            output += f"\n{range_name}: {accuracy:.3f}"
        
        output += f"""
\n=== Prediction Accuracy by Delay Level ===
\n{'Level':<12} {'Count':<8} {'Ratio':<8} {'MAE':<8} {'RMSE':<8} {'Dir Acc':<8}
{'-' * 60}
        """

        for level_name, metrics in delay_level_analysis.items():
            output += f"\n{level_name:<12} {metrics['count']:<8} {metrics['percentage']:<7.1f} "
            output += f"{metrics['mae']:<7.1f} {metrics['rmse']:<7.1f} {metrics['direction_accuracy']:<7.3f}"
        
        output += f"""
\n=== Practical Applicability Evaluation ===
\n• Within 1 minute accuracy: {overall_metrics['range_accuracies']['Within 1min']*100:.1f}% - Practical accuracy level
• Within 2 minutes accuracy: {overall_metrics['range_accuracies']['Within 2min']*100:.1f}% - Acceptable accuracy level
• Direction prediction accuracy: {overall_metrics['direction_accuracy']*100:.1f}% - Early/delay direction prediction
• R² score: {overall_metrics['r2']:.3f} - Overall prediction capability
        """
        return output