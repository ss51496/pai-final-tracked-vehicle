# WORKLOG

## 2026-10-21 段階0：環境の確認

### やったこと
- GitHub に private リポジトリを作成。プロフィールの氏名・公開メールは空、メールは非公開設定、コマンドラインでのメール露出 push のブロックを有効化。
- 作業場所は WSL2 の Ubuntu 内 `~/pai_final`（Docker へのマウントが速く、権限問題が起きにくいため）。
- git はこのリポジトリ内だけ匿名設定（GitHub の noreply アドレス）。
- コンテナ `pai_ros2` を `scripts/run_container.sh` で作成（`/workspace` にマウント、6080 / 9090 / 9876 を公開）。

### 実際に確認した環境
- コンテナ内：ユーザー `ubuntu`、HOME `/home/ubuntu`、DISPLAY `:0`
- Ignition Gazebo 6.16.0（Fortress）
- ros_gz 系と旧名 ros_ign 系の両方のパッケージあり
- システムプラグイン：diff-drive, joint-position-controller, joint-state-publisher, pose-publisher, imu, sensors, tracked-vehicle, track-controller
- 未確認：DiffDrive が左右に複数の関節を指定できるか（段階1で実機確認）
- `shapes.sdf` が noVNC 上で表示されることを目視で確認

### 遭遇した問題と解決
- WSL の Ubuntu に一般ユーザーがなく root のみ → 一般ユーザー `dev` を作成して既定にした（root 作成のファイルが編集不能になるのを防ぐ）。
- Ubuntu から `docker` が使えない → Docker Desktop の WSL integration を有効化。
- 既存の `pai_ros2` はマウントなし・ポート不足 → 削除して作り直した（コンテナの設定は後から変更できないため）。
