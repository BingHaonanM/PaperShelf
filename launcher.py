#!/usr/bin/env python3
"""PaperShelf Windows starter (also works on macOS/Linux). Stdlib only.

Bind to localhost on the first free port 8765-8775; open browser when ready.
Run directly with: python launcher.py
"""

import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

import app

PORT_RANGE = range(8765, 8776)


def bind_local_server():
    for port in PORT_RANGE:
        try:
            return ThreadingHTTPServer(('127.0.0.1', port), app.Handler)
        except OSError:
            continue
    raise OSError('本机端口 8765–8775 均已被占用。请关闭其他本地服务后重试。')


def open_browser_when_ready(url):
    for _ in range(40):
        try:
            with urllib.request.urlopen(url + '/api/libraries', timeout=0.6) as response:
                if response.status == 200:
                    if not webbrowser.open(url):
                        print('未能自动打开浏览器，请手动访问：' + url, flush=True)
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    print('浏览器没有自动打开，请手动访问：' + url, flush=True)


def main():
    os.chdir(Path(__file__).resolve().parent)
    app.init_storage()
    server = bind_local_server()
    url = 'http://127.0.0.1:' + str(server.server_port)
    print('文献管理地址：' + url, flush=True)
    print('文献数据目录：' + str(app.DATA), flush=True)
    print('只在本机 127.0.0.1 提供服务；按 Ctrl+C 退出。\n', flush=True)

    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nPaperShelf 已停止。', flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, PermissionError) as exc:
        print('PaperShelf 启动失败：' + str(exc), flush=True)
        raise SystemExit(1)
