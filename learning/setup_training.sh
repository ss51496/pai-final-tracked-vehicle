#!/bin/bash
# pai_training を clone し、自作の設定ファイルをリンクする（コンテナ内で実行）
#   docker exec -u ubuntu -w /workspace pai_ros2 bash learning/setup_training.sh
# pai_training の scripts/train.py は設定を configs/train_config.yaml から固定で読むため、
# 元のファイルを .orig に退避して、learning/ の設定へのシンボリックリンクに置き換える。
set -e
cd /workspace
[ -d pai_training ] || git clone --recursive https://github.com/matsuolab/pai_training pai_training
cd pai_training
if [ ! -L configs/train_config.yaml ]; then
  mv configs/train_config.yaml configs/train_config.yaml.orig
  ln -s /workspace/learning/train_config.yaml configs/train_config.yaml
fi
export PATH=$HOME/.pixi/bin:$PATH
command -v pixi > /dev/null || curl -fsSL https://pixi.sh/install.sh | bash
pixi install
echo "pai_training の準備ができました"
