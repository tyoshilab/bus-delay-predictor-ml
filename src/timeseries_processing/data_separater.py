class DataSeparater:
    def __init__(self):
        pass
    
    def X_Y_separate(self, data, target_col, feature_cols):
        X_all, y_all = [], []
        
        available_features = [col for col in feature_cols if col in data.columns]
        missing_features = [col for col in feature_cols if col not in data.columns]
        
        if missing_features:
            print(f"Warning: Missing features will be skipped: {missing_features}")
        
        print(f"Using features: {available_features}")
        
        X_all = data[available_features].values
        y_all = data[target_col].values

        return X_all, y_all, available_features