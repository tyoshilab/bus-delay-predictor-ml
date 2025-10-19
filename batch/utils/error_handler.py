"""
Error Handling Utilities

バッチ処理で使用するカスタムエラークラス
"""


class BatchError(Exception):
    """バッチ処理の基底エラー"""
    pass


class ConfigurationError(BatchError):
    """設定エラー"""
    pass


class DataProcessingError(BatchError):
    """データ処理エラー"""
    pass


class DatabaseError(BatchError):
    """データベースエラー"""
    pass


class APIError(BatchError):
    """API呼び出しエラー"""
    pass


class ValidationError(BatchError):
    """バリデーションエラー"""
    pass
