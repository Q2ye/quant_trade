#!/bin/bash
# 启动量化平台

# 设置环境变量
export PYTHONPATH=$(pwd)

# 根据参数启动不同模式
case "$1" in
  live)
    python main.py --mode live
    ;;
  events)
    python run_backtest.py --config config/events/$2.yaml
    ;;
  alpha)
    python main.py --mode alpha --strategy $2
    ;;
  *)
    echo "用法: $0 {live|backtest|alpha} [config]"
    exit 1
esac