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

入力例:「標準速度で1秒前進して」「右に1秒横移動して」「左に1秒回転して」。時間が不明な場合は確認が入ります。移動ツールは指定時間の実行と終了時のゼロ速度送信を待ち、完了・取消・失敗を返します。実機の完了は指令送信処理の完了であり、物理的な停止を確認した意味ではありません。移動中の新しい移動は拒否します。

| 入力 | 動作 |
|---|---|
| `/status` | LLMを使わず接続・移動状態・エラーを表示 |
| `/stop` | LLMを使わず実行中の移動を取り消し、ゼロ速度を送信・記録 |
| `/quit` / Ctrl-C | 終了時に移動の停止を試みる |

実機で移動が無効なら `/stop` も指令を送りません。移動実行・LLM応答待ちの間はチャット入力を処理できません。途中で取り消す場合はCtrl-Cで終了すると停止送信を試みます。別CLIの `stop` は他プロセスの送信ループを取り消せないため、対象の操作プロセスも停止してください。

チャット中は定周期の速度ログを表示せず、入力プロンプトを保ちます。指令ログの表示はモックの `move` コマンドで確認できます。

## 物体検出

`detect_objects` は、実機のカメラ画像を1枚撮影し、YOLOEで物体を探すツールです。検出だけを行い、機体は動かしません。`chat` で「青いボールはある？」のように聞くと、LLMが探す物体の英語名を付けて呼び出します。モックではカメラ画像を使わず、失敗を返します。

### 準備

検出用の依存関係（Ultralytics・PyTorchなど）は標準でインストールされます。共通の準備の `uv sync --frozen` だけで利用でき、追加インストールは不要です。Dockerイメージにも検出用の依存関係とOpenCV用のシステムライブラリを含みます。PyTorchを含むため、初回インストール・ビルドには時間とディスク容量が必要です。

モデルは既定で `weights/yoloe-26s-seg.pt` を使います。ファイルがない場合は、最初の検出時にUltralyticsが重みとテキストエンコーダーをダウンロードします（インターネット接続が必要です）。別の重みは `YOLOE_MODEL` で指定します。`weights/` と `*.pt` はGit管理対象外です。

Dockerの場合はイメージを再ビルドして起動します。

```sh
docker compose build
docker compose run --rm rosa chat
```

コンテナの作業ディレクトリは `/data` です。ホストの `./weights` を `/data/weights` にマウントするため、既存の `weights/yoloe-26s-seg.pt` をそのまま利用できます。重みがなければ同じホストディレクトリにダウンロードします。`weights/` がない場合は、起動前に `mkdir -p weights` で作成してください。

コンテナの実行ユーザーは既定でUID/GID `1000:1000` です。ホストのユーザーが異なる場合は、書き込み権限を合わせてビルドしてください。

```sh
docker compose build --build-arg APP_UID="$(id -u)" --build-arg APP_GID="$(id -g)"
```

テキストエンコーダー・キャッシュは名前付きボリューム `vision-data` に保持するため、`--rm` で終了しても次回に再利用できます。ルートファイルシステムは読み取り専用のまま、`/data` と一時領域のみ書き込み可能です。`docker compose down -v` はこのボリュームを削除しますが、ホストの `weights/` は残ります。別の重みを使う場合は `weights/` に配置し、`YOLOE_MODEL=weights/ファイル名.pt` を指定してください。

### 設定

静止画は、既存コンテナの `web_video_server` からHTTPで取得します。接続先のホストは `ROSBRIDGE_HOST` と共通です。次の項目は必要な場合だけ `.env` に設定します。

| 変数 | 既定値 | 内容 |
|---|---|---|
| `CAMERA_PORT` | `8080` | `web_video_server` のポート |
| `CAMERA_TOPIC` | `/image_raw` | 静止画を取得するROSトピック |
| `CAMERA_TIMEOUT_S` | `5` | 静止画取得の待ち時間（0より大きく60秒以下） |
| `YOLOE_MODEL` | `weights/yoloe-26s-seg.pt` | YOLOEの重みファイル |

### 静止画取得・MJPEG配信の確認

`<ホスト>` はTurboPiのアドレスです。PowerShellでは `curl` を `curl.exe` に置き換えてください。

```sh
# 静止画を1枚取得する（本アプリが使う経路）
curl -m 5 -o snap.jpg "http://<ホスト>:8080/snapshot?topic=/image_raw"

# 既存のMJPEG配信を5秒間受信する
curl -m 5 -s -o mjpeg.bin "http://<ホスト>:8080/stream?topic=/image_raw&type=mjpeg"
```

`snap.jpg` が画像として開け、`mjpeg.bin` のサイズが0より大きければ利用できます。MJPEG配信は終了しないため、5秒で打ち切られるのは正常です。本アプリは静止画だけを使い、MJPEGを使った推論は行いません。

### LLM経由の検出

検出だけを試す場合は `ENABLE_MOTION=false` を推奨します。

```dotenv
ROBOT_BACKEND=rosbridge
ENABLE_MOTION=false
```

```sh
uv run rosa-turbopi chat
```

入力例:「青いボールはある？」「何が見える？」。探す物体を指定しない場合は、一般的な物体と色付きのボールを探します。

結果の `state` は `completed`（検出処理完了）か `failed`（失敗）です。`completed` は、フレームID・画像サイズ・検出一覧（ラベル・信頼度・元画像のピクセル座標・左右3分割の位置）を含みます。見つからなかった場合は、`completed` と空の検出一覧を返します。`failed` は、`stage` が `capture`（撮影の失敗）か `inference`（検出の失敗）です。

検出は1枚の画像による結果で、距離は分かりません。写っていても検出されない場合や、色などを誤る場合があります。検出結果に基づく自動移動は行いません。

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
│   │   ├── motion.py              # 速度・時間制限・定周期実行・取消
│   │   ├── camera/                # 静止画の取得（実機はHTTP、モックは固定画像）
│   │   └── perception/            # YOLOEによる物体検出・検出結果の型
│   └── transport/
│       ├── rosbridge.py           # 実機へのWebSocket通信
│       └── mock.py                # ネットワークを使わない通信モック
├── tests/                         # 実機・外部LLM APIへ接続しないテスト
├── docs/
│   └── architecture.md            # 設計と既存コンテナとの関係
└── .github/workflows/
    └── ci.yaml                    # lint・テスト・パッケージビルド
```

詳細: [設計](docs/architecture.md)。

このリポジトリにはTurboPiのソース、SDK、コンテナイメージを含めません。

## Web UI（FastAPI / Jinja2 / htmx）

```sh
uv sync --frozen
ROBOT_BACKEND=mock uv run rosa-turbopi-web
```

ブラウザで http://127.0.0.1:8000 を開きます。上段にカメラと実行タイムライン、
下段に会話履歴と入力欄を表示します。過去の指示を選ぶと対応するツール実行を確認できます。
ツールの引数・結果は詳細を展開して確認できます。

`ROBOT_BACKEND=mock` は既存の動作モックとカメラのサンプル画像を使用します。
`rosbridge` は既存の実機接続を使用し、カメラ取得の実装までは「映像未接続」と表示します。
モックでもチャットには外部LLMの `OPENAI_API_KEY` と `LLM_MODEL` が必要です。
キーがなくても画面・カメラは表示でき、指示送信時には設定エラーを表示します。
ツール一覧には物体検出の `detect_objects` も表示します（[物体検出](#物体検出)）。検出枠の画面表示は未対応です。

停止ボタンはLLMを介さず、同じロボット接続で移動を取り消してゼロ速度を送信します。
同じ指示からの後続ツール実行も抑止します。LLM APIへの進行中の通信自体は完了を待つため、
その間は新しい指示を受け付けません。実機の物理的な停止確認を意味するものではありません。

初期版は単一操作セッション・単一ワーカーで使用します。会話と実行履歴はメモリ保持で、
再起動すると消去されます。認証は実装しておらず、既定ではループバックのみに公開します。
htmxとSSE拡張は同梱しているため、画面表示にCDN接続は不要です。

Web用コードは `web/`、HTMLに依存しない実行管理は `execution/`、
カメラ機能は `robot/camera/` に配置しています。

## 音声入力拡張

既存Web UIの外側に、PCのマイクによる音声入力を追加できます。
録音をOpenAIで文字起こしし、入力欄で確認・修正してから送信します。
`OPENAI_API_KEY` は会話と共用し、音声用モデルは `VOICE_TRANSCRIBE_MODEL` で指定できます。

```sh
uv sync --frozen
uv run rosa-turbopi-voice-web
```

既存Webサーバーを終了してから起動してください。
詳細・接続条件・制限は [音声入力拡張](docs/voice-input.md) を参照してください。
