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

### 2026-10-21 突堤の形状変更とカメラ視点（ユーザーの要望）
- 要望：頂上をもっと尖らせる、斜面をもっと急にする、視点を後ろから横にする。
- `gen_berm.py`：斜面 25° → **35°**、頂上の平らな部分 2.0 m → **0.3 m**、根元の面取り 12° → 17°。
- 懸念は「車輪の間隔（1.8 m）より頂上が狭いと、車体の腹が頂点に乗ってつかえる」こと。試験の結果、低速（スロットル 0.25）でも腹がつかえず越えられた。
- 試験結果（隔離環境、1回ずつ）：

| スロットル | 空中の時間 | 最高の z | 着地の最大 \|a\| |
|---|---|---|---|
| 1.0 | 0.94 s | 1.79 m（頂上より約0.46 m 高く跳ねる） | 26.5 m/s² |
| 0.5 | 0.50 s | 1.57 m | 145 m/s² |
| 0.25 | 0.34 s | 1.45 m | 213 m/s² |

  形状変更後は着地が下り斜面の先の平地になり、全開でも着地の衝撃は小さい。**評価の指標は着地の衝撃ではなく空中の時間（と最高の z）が向いている**（前回の指標案を修正）。
- 視点：launch が起動の8秒後に `/gui/move_to/pose` サービスで GUI カメラを横向き（ヨー +90°）に移動する。`side_view:=false` で無効化、`camera_xyz` で位置を変更。

### 遭遇した問題と解決（共有コンテナでの干渉）
- ユーザーが noVNC で動かしているシミュレーションと、私が試験用に起動した GUI なしのシミュレーションが**同じコンテナで重なり**、ROS のトピックと Gazebo のサービスを共有していた。試験の指令でユーザーの車両が動き、`/tank/state` に2台分の値が混ざった（x が 5〜11 と 65〜72 を交互に出力して発覚）。→ 試験用は `ROS_DOMAIN_ID=77`・`IGN_PARTITION=pai_test` で隔離する（`PAI_ISOLATED=1`、`scripts/test_sim.sh`）。停止は setsid でプロセスグループにして PID を記録し、グループごと止める（環境変数による判別は別ユーザーのプロセスで読めず失敗した）。
- 隔離前の試験データ（最大 |a| が 568〜1202 など）は2台の混在で無効。上の表は隔離後の再測定値。

### 2026-10-21 pai_training の読解と変換・学習の準備
- `/workspace/pai_training`（別 clone、git 管理外）の `rosbag2lerobot.py`、`crane_features.py`、`train.py`、`infer.py`、`debug_policy.py` を読んだ。
  - 変換：`.db3` から各トピックの時系列を読み、両トピックが存在する区間を fps の等間隔に区切って sample-and-hold で再サンプルする。特徴量は features ファイルで決まる。
  - **全エピソードを最長に合わせて最後のフレームで延ばしている**。突堤では通過後に止まり続ける区間が学習データに入ってしまうので、自作版では延ばさない（ACT は行動チャンクの終端を `action_is_pad` で扱える）。
  - 学習：`train.py` は設定を `configs/train_config.yaml` から固定で読む → `learning/setup_training.sh` で自作設定へのシンボリックリンクに置き換える。正規化はデータの統計から自動（推論時は元のスケールで出る）。
  - 推論：`select_action` を毎ステップ呼ぶ。`n_action_steps=1` なのでチャンクの先頭 1 個だけを実行する。
- 自作：`learning/`（`tank_features.py`、`conversion_config.yaml`、`rosbag2lerobot_tank.py`、`train_config.yaml`、`setup_training.sh`）、`policy_node.py`（10Hz、停止時に停止指令を送る）、`README.md`。
- 設計判断：fps は 10。`delta_timestamps` は 0.0〜1.5 秒の 16 個（チャンク 1.6 秒）。講義の設定は先頭が -0.1（過去の行動）だったが、本タスクは 0.0 から始めた。
- 環境：コンテナに GPU はなく CPU で学習する（20 コア、メモリ 31GB）。pixi は公式のインストーラで入れた（0.82.1）。依存パッケージの取得に時間がかかる（キャッシュが 5GB 超）。
- パイプライン試験：スクリプトによる自動操縦で 3 エピソードを `ros2 bag record` し、`.db3` ができることを確認（変換と学習の試験はこれから）。同じ手順でも着地の最大加速度は 26〜662 m/s² とばらつき、空中の時間は 0.22〜0.32 s で安定していた → **評価指標は空中の時間を使う**。
