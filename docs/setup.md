# セットアップ

READMEの手順に従い `.env` を作成してください。実機バックエンドでは既存rosbridgeが動作し、このホストから接続できることが前提です。モックではrosbridgeも機体も不要です。本プロジェクトは既存コンテナを起動・停止しません。

ComposeはLinuxのhost networkを使用します。同じPiのrosbridgeへは通常 `127.0.0.1`、別の機体ならそのアドレスを設定します。ポートは実環境の値を指定してください。TLS接続では `ROSBRIDGE_SECURE=true` を設定します。

`OPENAI_BASE_URL` は対応プロバイダー用の任意設定です。モデルはtool calling対応のものを `LLM_MODEL` に指定します。APIキーをリポジトリやDockerイメージに含めないでください。

自作コードの公開ライセンスは未選定のため、LICENSEはまだ追加していません。公開・配布前に選定してください。

## バックエンドの選択

`.env` の `ROBOT_BACKEND` は `rosbridge`（既定）か `mock` を指定します。シェルで指定した環境変数が `.env` より優先されます。

```sh
# 実機の読み取り。LLM設定は不要
ROBOT_BACKEND=rosbridge uv run rosa-turbopi check
ROBOT_BACKEND=rosbridge uv run rosa-turbopi battery

# 模擬移動。LLM設定は不要
ROBOT_BACKEND=mock uv run rosa-turbopi move --vx 0.05 --duration 1

# モックの日本語対話。LLM設定が必要
ROBOT_BACKEND=mock uv run rosa-turbopi chat
```

モックは機体へ接続しませんが、`chat` は設定したLLM APIを利用します。LLMを使わず確認する場合は `move`、`check`、`battery` を使います。`stop` コマンドはそのCLIプロセスの操作だけが対象です。別プロセスで動くチャットの模擬移動を止めるには、そのチャットで `/stop` を入力してください。

## チャット内のコマンド

| 入力 | 動作 |
|---|---|
| `/status` | 接続・バックエンド・移動状態・エラーを表示 |
| `/stop` | モックの移動を取り消し、ゼロ速度を記録 |
| `/quit` / Ctrl-C | 終了し、モックの移動を停止して接続を閉じる |

実機バックエンドの `/stop` は停止指令を送信しません。実機走行を有効化する設定はありません。
