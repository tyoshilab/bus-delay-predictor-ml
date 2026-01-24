import pandas as pd
import const
import os
import json

class Split:
    def __init__(
        self,
        train_size: float = 0.7
    ):
        self.df_train = pd.DataFrame()
        self.df_test = pd.DataFrame()
        self.split_info = ''
        self.train_size = train_size
        self.output_dirr = const.PROCESSED_DATA_DIR

    def split_time_series(
        self,
        df: pd.DataFrame
    ) -> None:

        unique_dates = sorted(df['start_date'].unique())
        n_dates = len(unique_dates)

        train_end_idx = int(n_dates * self.train_size)

        train_dates = unique_dates[:train_end_idx]
        test_dates = unique_dates[train_end_idx:]

        self.df_train = df[df['start_date'].isin(train_dates)].copy()
        self.df_test = df[df['start_date'].isin(test_dates)].copy()

        self.split_info = {
            'train_dates': list(train_dates),
            'test_dates': list(test_dates),
            'train_date_range': (train_dates[0], train_dates[-1]) if train_dates else None,
            'test_date_range': (test_dates[0], test_dates[-1]) if test_dates else None,
            'train_samples': len(self.df_train),
            'test_samples': len(self.df_test),
            'train_ratio_actual': len(self.df_train) / len(df),
            'test_ratio_actual': len(self.df_test) / len(df),
        }


    def print_split_info(self) -> None:
        print("=" * 50)
        print("Time Series Split Information")
        print("=" * 50)

        for name in ['train', 'test']:
            date_range = self.split_info.get(f'{name}_date_range')
            samples = self.split_info.get(f'{name}_samples', 0)
            ratio = self.split_info.get(f'{name}_ratio_actual', 0)

            if date_range:
                print(f"\n{name.upper()}:")
                print(f"  Date range: {date_range[0]} ~ {date_range[1]}")
                print(f"  Samples: {samples:,} ({ratio:.1%})")

        print("=" * 50)


    def save_split_data(self) -> None:

        os.makedirs(self.output_dirr, exist_ok=True)
                
        # save dataset
        self.df_train.to_parquet(f'{self.output_dirr}/train.parquet', index=False)
        self.df_test.to_parquet(f'{self.output_dirr}/test.parquet', index=False)

        # save split info
        split_info_serializable = self.split_info.copy()
        for key in ['train_dates', 'test_dates']:
            if key in split_info_serializable:
                split_info_serializable[key] = [str(d) for d in split_info_serializable[key]]
        with open(f'{self.output_dirr}/split_info.json', 'w') as f:
            json.dump(split_info_serializable, f, indent=2, default=str)

        print(f"Saved split data to {self.output_dirr}")


    def load_split_data(self) -> None:

        # load dataset
        self.df_train = pd.read_parquet(f'{self.output_dirr}/train.parquet')
        self.df_test = pd.read_parquet(f'{self.output_dirr}/test.parquet')
        
        # load split info
        with open(f'{self.output_dirr}/split_info.json', 'r') as f:
            self.split_info = json.load(f)

        print(f"Load split data")