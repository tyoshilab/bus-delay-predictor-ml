#!/bin/bash
# =====================================================
# Cron Scheduler for GTFS Realtime Fetch
# =====================================================
#
# Cron設定例:
#   # 5分ごとに実行
#   */5 * * * * /path/to/GTFS/batch/schedulers/cron_fetch.sh
#
# ログ確認:
#   tail -f /path/to/GTFS/batch/logs/gtfs_fetch_YYYYMMDD.log
# =====================================================

# プロジェクトルートディレクトリ（このスクリプトの2階層上）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Python仮想環境のパス（使用している場合）
VENV_PATH="${PROJECT_ROOT}/venv"

# 環境変数読み込み
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
fi

# Python仮想環境をアクティベート（使用している場合）
if [ -d "$VENV_PATH" ]; then
    source "${VENV_PATH}/bin/activate"
fi

# ジョブ実行
cd "$PROJECT_ROOT" || exit 1

python3 batch/run.py fetch "$@"

exit $?
