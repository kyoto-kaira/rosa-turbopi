# セットアップ

READMEの手順に従い `.env` を作成してください。実機バックエンドでは既存rosbridgeが動作し、このホストから接続できることが前提です。モックではrosbridgeも機体も不要です。本プロジェクトは既存コンテナを起動・停止しません。

ComposeはLinuxのhost networkを使用します。同じPiのrosbridgeへは通常 `127.0.0.1`、別の機体ならそのアドレスを設定します。ポートは実環境の値を指定してください。TLS接続では `ROSBRIDGE_SECURE=true` を設定します。

`OPENAI_BASE_URL` は対応プロバイダー用の任意設定です。モデルはtool calling対応のものを `LLM_MODEL` に指定します。APIキーをリポジトリやDockerイメージに含めないでください。

自作コードの公開ライセンスは未選定のため、LICENSEはまだ追加していません。公開・配布前に選定してください。

## バックエンドの選択

`ENABLE_MOTION` は既定で `true` です。実機の読み取りだけを行う場合は、以下の例のように `false` を指定してください。

`.env` の `ROBOT_BACKEND` は `rosbridge`（既定）か `mock` を指定します。シェルで指定した環境変数が `.env` より優先されます。

実機の読み取りでは `.env` に次を設定します。

```dotenv
ROBOT_BACKEND=rosbridge
ENABLE_MOTION=false
```

```sh
uv run rosa-turbopi check
uv run rosa-turbopi battery
```

模擬移動では `.env` を変更します。

```dotenv
ROBOT_BACKEND=mock
ENABLE_MOTION=false
```

```sh
uv run rosa-turbopi move --vx 0.5 --duration 1
uv run rosa-turbopi chat
```

設定変更後はCLIを再起動してください。Docker Composeも `env_file: .env` から読み込みます。起動コマンドにバックエンドや有効化設定を付ける必要はありません。既にシェルでexportした同名の変数はローカル実行では優先されるので、`.env` を使う際は `unset ROBOT_BACKEND ENABLE_MOTION` で解除してください。

モックは機体へ接続しませんが、`chat` は設定したLLM APIを利用します。LLMを使わず確認する場合は `move`、`check`、`battery` を使います。`stop` コマンドはそのCLIプロセスの操作だけが対象です。別プロセスで動くチャットの模擬移動を止めるには、そのチャットで `/stop` を入力してください。

## チャット内のコマンド

| 入力 | 動作 |
|---|---|
| `/status` | 接続・バックエンド・移動状態・エラーを表示 |
| `/stop` | モックの移動を取り消し、ゼロ速度を記録 |
| `/quit` / Ctrl-C | 終了し、モックの移動を停止して接続を閉じる |

実機バックエンドの移動と停止にはENABLE_MOTION=trueが必要です。通信断時の停止保証はありません。詳しい試験手順と制限はREADMEを参照してください。

## タイムアウトとトピック

`.env` の `ROSBRIDGE_TIMEOUT_S=5` は接続とバッテリー読み取りの待ち時間です。0より大きく60秒以下の有限値を指定します。走行の自動停止期限ではありません。バッテリーのトピック名 `/ros_robot_controller/battery` と型 `std_msgs/msg/UInt16` は `settings.py` の既定値です。YAML設定ファイルは不要です。
