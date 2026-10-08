#!/bin/bash
# PaperShelf · macOS one-click launcher
# This script only starts the local service. All library data stays on this Mac.

set -u
cd "$(dirname "$0")" || exit 1

echo "=========================================="
echo " PaperShelf · Mac 本地文献管理"
echo "=========================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "未找到 Python 3。请先安装 Python 3.9 或更新版本。"
    echo "官方下载：https://www.python.org/downloads/macos/"
    echo
    read -r -p "按回车键关闭窗口..." _
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    echo "需要 Python 3.9 或更新版本。"
    python3 --version 2>&1
    echo
    read -r -p "按回车键关闭窗口..." _
    exit 1
fi

# Keep the private installation separate from another running instance by
# selecting an available localhost port. Do not access other project folders.
PORT=$(python3 - <<'PY'
import socket
for port in range(8765, 8776):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            continue
        print(port)
        break
PY
)

if [ -z "$PORT" ]; then
    echo "8765–8775 端口均已占用。请停止其他本地服务后重试。"
    read -r -p "按回车键关闭窗口..." _
    exit 1
fi

URL="http://127.0.0.1:${PORT}"
echo "文献数据目录：$(pwd)/data"
echo "访问地址：${URL}"
echo "本服务仅监听本机 127.0.0.1，不向互联网发送文献。"
echo "关闭服务：在此终端窗口按 Control + C。"
echo

# Open the browser only after this instance responds. Start the HTTP server
# in the foreground so closing it with Control+C also stops the service.
(
    for _attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        if curl --silent --show-error --fail --max-time 1 "${URL}/api/libraries" >/dev/null 2>&1; then
            open "$URL" >/dev/null 2>&1 || echo "请手动在浏览器打开：${URL}"
            exit 0
        fi
        sleep 0.5
    done
) &
WATCH_PID=$!

python3 app.py --port "$PORT"
RESULT=$?
kill "$WATCH_PID" 2>/dev/null || true
wait "$WATCH_PID" 2>/dev/null || true

if [ "$RESULT" -ne 0 ]; then
    echo
    echo "服务未能正常启动（退出码 $RESULT），请检查上面的报错。"
    read -r -p "按回车键关闭窗口..." _
fi
exit "$RESULT"
