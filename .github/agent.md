# 1. Project Overview
このプロジェクトは、バスの運行データと気象データを統合し、機械学習を用いて到着遅延を予測するパイプラインを構築することを目的としています。 データ取得、前処理、複数のモデル（XGBoost, LSTM, ST-GNN）による学習、およびエラー分析までを一貫して行います。

# 2. Directory Structure & Conventions
プロジェクトのファイル構造を理解し、適切な場所にコードを配置してください。

- `notebook/`: 実験、データ探索、プロトタイプ作成用。
    - 番号順（00〜07）に実行される設計。
    - 複雑なロジックはここに直接書かず、`src/` へ移行することを優先する。

- `src/`: 再利用可能なプロダクションコード。
    - `config.py`: 定数やディレクトリパス、特徴量リストの管理。
    - `data_connection/`: データベース接続（SQL）ロジック。
    - `data_splitter.py`: 時系列を考慮したデータ分割。
    - `utils.py`: 共通ユーティリティ関数。

- `tests/`: テストコード（新設）。
    - `unit/`: 個別の関数やクラスのテスト。
    - `integration/`: データの流れやパイプラインのテスト。

# 3. Development Rules
- **Source over Notebook**: ノートブックで2回以上再利用されるロジック、または複雑な処理は必ず `src/` 内のモジュールに定義し、ノートブックからはそれをインポートして使用する。

- **Configuration Management**: パスやハイパーパラメータ、カラム名の文字列を直接ハードコードしない。必ず `src/config.py` または `src/const.py` を経由する。

- **Typing**: Pythonの型ヒントを積極的に活用し、コードの可読性と堅牢性を高める。

# 4. TDD (Test Driven Development) Workflow
新しい機能の追加や `src/` 配下のコードを修正する場合、以下のサイクルを厳守してください。

1. **Red**: まず `tests/` 配下に、期待する動作を定義した失敗するテストコードを書く。
2. **Green**: テストをパスさせるための最小限の実装を行う。
3. **Refactor**: コードを整理し、DRY（Don't Repeat Yourself）原則を適用する。リファクタリング後もテストがパスすることを確認する。

- 使用ツール: `pytest`

## イテレーション単位
- 機能を最小単位に分割し、各イテレーションで１つの機能を完成させます。
- 各イテレーションでbuild, test, lintなどを一通りパスしたことを確認し、コミット。

# 5. Technical Stack
- **Language**: Python 3.x
- **Data Analysis**: Pandas, NumPy, Scikit-learn
- **ML/DL**: XGBoost, PyTorch (ST-GNN, LSTM)
- **Database**: PostgreSQL (via DatabaseConnector)

# 6. Specific Instructions for Agent
- **実装提案の際**: 「まずテストコードを書きましょうか？」と提案し、TDDサイクルを促してください。
- **リファクタリング時**: ノートブック内のセルが長くなっている場合、`src/` への抽出とそれに対するテスト作成を提案してください。
- **データ整合性**: 遅延予測において「未来のデータが学習に含まれる（リーク）」ことは致命的です。`data_splitter.py` のロジックを常に参照し、時系列的な整合性を保ってください。
- **環境変数**: APIキーやDB接続情報は直接出力せず、`.env` ファイル（`.env.example` 参照）を利用するよう案内してください。
