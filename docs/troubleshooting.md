# トラブル対応

- 接続エラー: ROSBRIDGE_HOST / PORT、既存rosbridgeの起動状態、ネットワーク到達性を確認します。
- バッテリーのタイムアウト: トピック名・型・publisherを確認します。読み取り失敗時には成功値を返しません。
- chatの設定エラー: OPENAI_API_KEY と LLM_MODEL を設定します。check / batteryには不要です。
- ROSA更新でrclpyのエラー: agentの独自ツール登録フックと上流APIの変更を確認します。ROSの導入で回避する設計ではありません。
