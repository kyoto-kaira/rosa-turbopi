# rosa-turbopi

日本語のCLIから [NASA JPL ROSA](https://github.com/nasa-jpl/rosa) を使い、既存TurboPiのrosbridgeへ接続する独立したPythonアプリです。既存コンテナの変更、ROSのローカルインストール、ベンダーSDKは不要です。

実機は **接続状態とバッテリーの読み取りのみ**。モックでは時間指定の移動・停止を確認できます。実機への移動・停止指令はコード側で無効です。アプリ切替は未実装です。

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

## 模擬移動（実機には接続しません）

```sh
ROBOT_BACKEND=mock uv run rosa-turbopi move --vx 0.05 --duration 1
ROBOT_BACKEND=mock uv run rosa-turbopi chat
# Dockerでも利用できます
ROBOT_BACKEND=mock docker compose run --rm rosa chat
```

チャットでは「ゆっくり1秒前進して」「止まって」と入力します。`/stop` はLLMを使わず模擬移動を停止します。移動開始と完了は区別し、接続状態ツールで移動の状態を取得できます。

モックの速度上限は並進合成速度0.1 m/s、旋回0.3 rad/s、最大3秒、送信周期10 Hzです。並進はvx正が前、vy正が左、旋回はwz正が左です。表示される速度指令やバッテリー値は模擬値です。

`rosbridge` バックエンドには移動ツールを登録しません。`move` / `stop` コマンドも接続前に拒否します。実機へのpublish機能は実装していないため、環境変数で実機走行を有効化できません。
