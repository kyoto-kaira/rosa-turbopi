# rosa-turbopi

日本語のCLIから [NASA JPL ROSA](https://github.com/nasa-jpl/rosa) を使い、TurboPiを操作する独立したPythonアプリです。実機では既存コンテナのrosbridgeへ接続し、モックでは機体に接続せず操作を確認できます。既存コンテナの変更、ローカルへのROSインストール、ベンダーSDKは不要です。

## 共通の準備

リポジトリのルートで実行してください。ローカル実行にはPython 3.11 / 3.12とuv、コンテナ実行にはDocker Compose（Linux / Raspberry Pi）を使用します。

`.env` がない場合だけ、設定例をコピーします。

```sh
cp .env.example .env
```

ローカル実行では依存関係をインストールします。

```sh
uv sync --frozen
```

Dockerで実行する場合は専用イメージをビルドします。

```sh
docker compose build
```

`chat` を使う場合は `.env` に `OPENAI_API_KEY` とtool calling対応の `LLM_MODEL` を設定します。`OPENAI_BASE_URL` は別の対応エンドポイントを使う場合の任意設定です。`check`、`battery`、`move`、`stop` はLLMを使いません。

設定変更後はCLIを再起動してください。ローカル実行ではシェルの環境変数が `.env` より優先されます。以前exportした設定が残っている場合は `unset ROBOT_BACKEND ENABLE_MOTION` で解除します。`.env` はGit管理対象外です。

## 実機での実行

既存TurboPiのrosbridgeが起動済みで、このホストから接続できることが前提です。本アプリは既存コンテナを起動・停止しません。

### 設定

`.env` を次のように設定します。同じPiからの接続例です。別の機体なら接続先を変更してください。

```dotenv
ROBOT_BACKEND=rosbridge
ENABLE_MOTION=true
ROSBRIDGE_HOST=127.0.0.1
ROSBRIDGE_PORT=9090
ROSBRIDGE_SECURE=false
ROSBRIDGE_TIMEOUT_S=5
```

移動・停止は既定で有効です。読み取りだけを行う場合は `ENABLE_MOTION=false` に変更してください。。`ROSBRIDGE_TIMEOUT_S` は接続・読み取りの待ち時間であり、走行の停止期限ではありません。

### 接続・バッテリーの確認

```sh
uv run rosa-turbopi check
uv run rosa-turbopi battery
```

Dockerの場合:

```sh
docker compose run --rm rosa check
docker compose run --rm rosa battery
```

バッテリーは生値を返します。単位・残量換算は未確認です。

### 移動・日本語対話


```sh
uv run rosa-turbopi move --vx 0.5 --duration 0.5
uv run rosa-turbopi stop
uv run rosa-turbopi chat
```

Dockerの場合:

```sh
docker compose run --rm rosa move --vx 0.5 --duration 0.5
docker compose run --rm rosa stop
docker compose run --rm rosa chat
```

`simulated=false` は実機への指令送信を示します。実際に移動・停止したことをセンサーで確認したという意味ではありません。

## モックでの実行

機体・rosbridgeは不要です。速度指令はメモリに記録し、ロボットへのネットワーク接続は行いません。モックでも `chat` は設定した外部LLM APIを利用します。

### 設定

`.env` を次のように変更します。モックの移動は `ENABLE_MOTION=false` でも利用できます。

```dotenv
ROBOT_BACKEND=mock
ENABLE_MOTION=false
```

### 移動・日本語対話

```sh
# LLMなしで指令ログと終了状態を確認
uv run rosa-turbopi move --vx 0.5 --duration 1

# 日本語で操作
uv run rosa-turbopi chat
```

Dockerの場合:

```sh
docker compose run --rm rosa move --vx 0.5 --duration 1
docker compose run --rm rosa chat
```

`simulated=true` は模擬操作を示します。バッテリー取得も模擬値（固定7400）を返します。

## 操作とチャット内コマンド

実機の移動が有効な場合とモックで、同じ移動ツールを利用できます。

| ツール | 操作 | 既定の指令値 |
|---|---|---|
| `move_forward` / `move_backward` | 前進 / 後退 | 0.5 m/s |
| `move_left` / `move_right` | 左 / 右へ横移動 | 0.5 m/s |
| `rotate_left` / `rotate_right` | その場で左 / 右回転 | 5.0 rad/s |
| `move_for` | vx・vy・wzを指定した移動 | 引数で指定 |
| `stop` | 移動取消・ゼロ速度送信 | 0 |

並進の合成速度は0.4〜0.9 m/s（停止の0を除く）、旋回は最大7.0 rad/s、継続時間は0より大きく最大3秒、送信周期は10 Hzです。指令値は実測速度の保証ではありません。方向別ツールは正の速度を受け取り、前進・左横移動・左回転をそれぞれvx・vy・wzの正方向として扱います。

入力例:「標準速度で1秒前進して」「右に1秒横移動して」「左に1秒回転して」。時間が不明な場合は確認が入ります。移動はバックグラウンドで実行し、開始応答と完了状態を区別します。移動中の新しい移動は拒否します。

| 入力 | 動作 |
|---|---|
| `/status` | LLMを使わず接続・移動状態・エラーを表示 |
| `/stop` | LLMを使わず実行中の移動を取り消し、ゼロ速度を送信・記録 |
| `/quit` / Ctrl-C | 終了時に移動の停止を試みる |

実機で移動が無効なら `/stop` も指令を送りません。LLM応答待ちの間はチャット入力を処理できません。別CLIの `stop` は他プロセスの送信ループを取り消せないため、対象の操作プロセスも停止してください。

チャット中は定周期の速度ログを表示せず、入力プロンプトを保ちます。指令ログの表示はモックの `move` コマンドで確認できます。

## 開発・検証

```sh
uv run rosa-turbopi --help
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

テストは通信モックとテスト用LLMを使用し、実機・外部LLM APIには接続しません。

## 構成

`cli → ROSA → tools → robot → transport（既存rosbridge / モック）`

### ディレクトリ構成

```text
rosa-turbopi/
├── README.md
├── pyproject.toml                 # 依存関係・CLI定義
├── uv.lock                        # 依存バージョン固定
├── Dockerfile                     # ROSA専用イメージ
├── compose.yaml                   # 既存コンテナとは独立した起動設定
├── .env.example                   # 接続先・LLM・バックエンド・移動設定の例
├── src/rosa_turbopi/
│   ├── cli.py                     # 日本語対話・直接操作・終了処理
│   ├── settings.py                # .envの読込
│   ├── agent.py                   # ROSA・LLM・独自ツールの組立
│   ├── prompts.py                 # ロボット用の指示・単位・制約
│   ├── tools/
│   │   ├── status.py              # 接続状態・バッテリーの取得ツール
│   │   └── motion.py              # 前後左右・回転・停止ツール
│   ├── robot/
│   │   ├── client.py              # ロボット操作の窓口
│   │   └── motion.py              # 速度・時間制限・定周期実行・取消
│   └── transport/
│       ├── rosbridge.py           # 実機へのWebSocket通信
│       └── mock.py                # ネットワークを使わない通信モック
├── tests/                         # 実機・外部LLM APIへ接続しないテスト
├── docs/
│   ├── architecture.md            # 設計と既存コンテナとの関係
│   ├── robot-interface.md         # ROSトピック・型・対応状況
│   ├── setup.md                   # 設定・起動・チャット内コマンド
│   └── troubleshooting.md         # 接続・操作・表示のトラブル対応
└── .github/workflows/
    └── ci.yaml                    # lint・テスト・パッケージビルド
```

詳細: [設計](docs/architecture.md)、[接続仕様](docs/robot-interface.md)、[セットアップ](docs/setup.md)、[トラブル対応](docs/troubleshooting.md)。

このリポジトリにはTurboPiのソース、SDK、コンテナイメージを含めません。
