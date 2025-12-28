
import os
import pandas as pd

def load_data():
    """Load the base datasets from /workspace/notebook"""
    base_path = '/workspace/GTFS/data_analysis/base_data/'
    # Check if files exist, otherwise try to find them or warn
    base_df = pd.DataFrame()
    for file in os.listdir(base_path):
        file_path = os.path.join(base_path, file)
    
        if not os.path.exists(file_path):
            print(f"Warning: Data files not found in {base_path}")
            return None
        
        base_df = pd.concat([base_df, pd.read_csv(file_path)], ignore_index=True)
        
    base_df['start_date'] = base_df['start_date'].astype(str)
    return base_df