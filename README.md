# rosa-turbopi

日本語のCLIから [NASA JPL ROSA](https://github.com/nasa-jpl/rosa) を使い、既存TurboPiのrosbridgeへ接続する独立したPythonアプリです。既存コンテナの変更、ROSのローカルインストール、ベンダーSDKは不要です。

初期版は **接続状態とバッテリーの読み取りのみ**。走行・アプリ切替はまだ提供しません。実機の通信断時の停止挙動を確認してから追加します。

## Dockerで起動（Linux / Raspberry Pi）

前提: Docker Compose、既存のrosbridge WebSocketエンドポイント、対話用のtool calling対応LLM。

```sh
cp .env.example .env
# .env に ROSBRIDGE_HOST / PORT、OPENAI_API_KEY、LLM_MODEL を設定
# 9090 は設定例。実環境のrosbridgeポートを確認してください。
docker compose build
docker compose run --rm rosa check
docker compose run --rm rosa battery
docker compose run --rm rosa chat
```

`chat` では「接続状態を教えて」「バッテリーを教えて」と入力できます。`/quit` または Ctrl-C で終了します。`check` と `battery` はLLMを使用しません。

## ローカル開発

Python 3.11 / 3.12 と uv を使用します。リポジトリのルートで実行してください。

```sh
uv sync --frozen
uv run rosa-turbopi --help
uv run ruff check .
uv run pytest
```

ローカル設定は `config/turbopi.local.yaml` として作り、`.env` の `TURBOPI_CONFIG` に指定できます。`.env` とローカル設定はGit管理対象外です。

## 構成

`cli → ROSA → tools → robot → transport → 既存rosbridge`

- `src/rosa_turbopi/agent.py`: 独自ツールのみを登録するROSAアダプター
- `tools/`: LLMに公開する操作
- `robot/`: ロボットの操作・状態取得
- `transport/`: roslibpyによるWebSocket通信
- `config/`: 公開可能なインターフェース設定例
- `tests/`: 実機やLLMを使わない検証

詳細: [設計](docs/architecture.md)、[接続仕様](docs/robot-interface.md)、[セットアップ](docs/setup.md)、[トラブル対応](docs/troubleshooting.md)。

このリポジトリにはTurboPiのソース、SDK、コンテナイメージを含めません。ROSA等の依存ライブラリにはそれぞれのライセンスが適用されます。自作コードの公開ライセンスは選定前です。
