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

## 2026-10-21 段階1：車両モデルと操縦系（実装）

### 作ったもの
- `ros2_ws/src/tank_il`（ament_python）：モデル生成スクリプト、平地 world（`worlds/flat.sdf`）、bridge 設定、`tank_driver`、`state_publisher`、`teleop_tank`、launch。
- 車両モデルは `tools/gen_tank_model.py` で生成（片側7輪×2、砲塔＋砲身、IMU）。パラメータは架空の値。慣性は形状と質量から計算。14輪の定義を手書きすると間違えやすいので、生成スクリプトにした。
- 履帯は見た目用の箱。衝突判定は車輪（円柱）と車体、砲塔、砲身。
- 操縦：`/tank/command = [throttle, steering, turret_angle]`。ハンドルは右が正、砲塔角は左回りが正。teleop は 20Hz で配信し続ける。
- 安全のため `tank_driver` に 0.5 秒のウォッチドッグを入れた（指令が途絶えたら停止）。teleop や方策が落ちたときに暴走しない。

### 動作確認（トピックの値）
- 前進 throttle 0.5 → 2.0 m/s、1.0 → 4.0 m/s（v_max = 4.0）、後退 -2.0 m/s。
- その場旋回：指令 1.5 rad/s に対し約 1.4 rad/s（約93%）、位置ずれ 0.12 m。右が時計回り。
- 砲塔：±90° に回り `/tank/state` に反映。平地で z=0.32、pitch=0。

### 遭遇した問題と解決
- **bridge が config_file に非対応**（この環境の ros_gz_bridge）→ `config/bridge.yaml` を正本にして、launch が読み込んで引数に展開する。
- **launch が `libexec directory does not exist` で失敗** → `setup.cfg` で `install_scripts=$base/lib/tank_il` を指定（ament_python の決まり）。
- **PosePublisher が真値の位置姿勢として使えなかった**：リンク姿勢は車体からの相対値で、モデル自身の世界座標姿勢は出ない。SceneBroadcaster の `pose/info` は bridge で名前が失われる。→ **OdometryPublisher**（`/odom_gt`、dimensions=3）で世界座標の真値（z を含む）を取る。DiffDrive の `/odom` は車輪の積分で滑りを含むので、v_forward 用として別に残す。
- **ゾンビプロセス**：`bash -c 'pkill -f "ign gazebo"'` は pkill が自分のコマンドラインに一致して途中で終了し、Gazebo が3世代残った（トピックのレートが倍々になって気づいた）。→ `scripts/kill_sim.sh`（`[i]gn` のように先頭を [] で囲んで自己一致を避ける）。
- `/joint_states` が約1kHz（Gazebo の毎ステップ配信でレート指定不可）。`/tank/state` は 20Hz で配信するので実害なし。

### 設計判断
- 観測の pitch は IMU のクォータニオンから求め、**機首上げ（登り）を正**にした（REP-103 の符号を反転。ピッチ角とスロットルの対応を人が見て分かりやすくするため）。
- `state_publisher` は 4 つの入力がそろうまで配信しない（0 埋めの偽の観測を記録しないため）。
- world 名は全 world で `course` に統一（トピック名やリセット用のサービス名を共通にするため）。

## 2026-10-21 段階2：突堤の world と「跳ねる」ことの確認

### 作ったもの
- `tools/gen_berm.py` → `models/berm/`（台形の山：高さ1.0m、斜面25°、頂上2.0m）。断面（x-z）の多角形を y 方向に押し出す polyline で作る。根元に小さな面取りを入れて、車体前端が地面に刺さらないようにした。頂上の縁は鋭いままにした。
- `worlds/berm.sdf`（world 名は course）、`scripts/reset_tank.sh`（`ign service` の `/world/course/set_pose`、駆動停止と砲塔 0° も行う）。

### 確認結果：全開のまま頂上を越えると跳ねる（v_max=4 m/s、一定スロットルで通過、1回ずつの測定）
| スロットル | 速度 | 空中の時間（IMU の \|a\|<3） | 着地の最大 \|a\| | 通過後の最小ピッチ |
|---|---|---|---|---|
| 1.0 | 4 m/s | 0.72 s | 642 m/s² | -42.7° |
| 0.75 | 3 m/s | 0.82 s | 218 m/s² | -20.6° |
| 0.5 | 2 m/s | 0.58 s | 93 m/s² | -25.8° |

熟練者の手順（全開で登る → 停止 → 下りはスロットル0.25）：最大 \|a\| = 144〜153 m/s²、空中 0.26〜0.42 s。斜面の途中でも頂上でも停止して保持できた。

### 考察・設計判断
- 頂上の縁が鋭いため、低速でも縁を越える瞬間に機首が落ちて「空中」と判定される。**空中の時間は「跳ねた」の指標としては弱い**。差が大きく出るのは着地の衝撃（最大 \|a\|）なので、評価の指標の候補にする。ただし接触計算のスパイクで低速でも 100 m/s² 台は出るため、閾値は複数回の測定で決める。
- **「下りは重力に任せる」は再現できない**：DiffDrive は車輪を速度制御するので、スロットル 0 では車輪が止まり、25° の斜面でも保持される。そのため、下りは低いスロットル（0.25）でゆっくり進める手順にした。
- 試験用のスクリプトは `logs/`（git 管理外）に置いた。
