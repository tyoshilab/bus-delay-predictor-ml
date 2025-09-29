#!/bin/bash
# Vancouver Weather Scraper Setup Script

echo "=== Vancouver Weather Scraper セットアップ ==="

# 仮想環境の確認
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ 仮想環境: $VIRTUAL_ENV"
else
    echo "⚠️  仮想環境が有効化されていません"
fi

# 依存関係インストール
echo "📦 依存関係をインストール中..."
pip install -r /workspace/GTFS/climate/scraper_requirements.txt

# Playwrightブラウザインストール
echo "🌐 Playwrightブラウザをインストール中..."
playwright install chromium

# ダウンロードディレクトリ作成
mkdir -p /workspace/GTFS/climate/downloads
echo "📁 ダウンロードディレクトリ作成完了"

# 実行権限付与
chmod +x /workspace/GTFS/climate/weather_scraper.py

echo "✅ セットアップ完了！"
echo ""
echo "=== 使用方法 ==="
echo "単発実行:"
echo "  python /workspace/GTFS/climate/weather_scraper.py --mode single"
echo ""
echo "定期実行（1時間ごと）:"
echo "  python /workspace/GTFS/climate/weather_scraper.py --mode schedule"
echo ""
echo "DBロードなしで実行:"
echo "  python /workspace/GTFS/climate/weather_scraper.py --mode single --no-db"