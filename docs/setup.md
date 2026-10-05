# セットアップ

READMEの手順に従い `.env` を作成してください。既存rosbridgeが動作し、このホストから接続できることが前提です。本プロジェクトは既存コンテナを起動・停止しません。

ComposeはLinuxのhost networkを使用します。同じPiのrosbridgeへは通常 `127.0.0.1`、別の機体ならそのアドレスを設定します。ポートは実環境の値を指定してください。TLS接続では `ROSBRIDGE_SECURE=true` を設定します。

`OPENAI_BASE_URL` は対応プロバイダー用の任意設定です。モデルはtool calling対応のものを `LLM_MODEL` に指定します。APIキーをリポジトリやDockerイメージに含めないでください。

自作コードの公開ライセンスは未選定のため、LICENSEはまだ追加していません。公開・配布前に選定してください。
