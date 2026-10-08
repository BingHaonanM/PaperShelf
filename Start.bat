@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 (
    echo 无法进入 PaperShelf 程序目录。
    pause
    exit /b 1
)

echo ==========================================
echo  PaperShelf - Windows 本地文献管理
echo ==========================================
echo.

if not exist "launcher.py" (
    echo 缺少 launcher.py，请使用完整安装包，或同时复制 Start.bat 和 launcher.py。
    pause
    popd
    exit /b 1
)

rem Prefer the Python launcher; fall back to python/python3 on PATH.
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto :start
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :start
)
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto :start
)

echo 未找到 Python 3.9 或更新版本。
echo 请从 https://www.python.org/downloads/windows/ 安装 Python。
echo 安装时勾选 Add python.exe to PATH，然后重新运行 Start.bat。
echo.
pause
popd
exit /b 1

:start
echo 启动本机服务，浏览器将自动打开。
echo 关闭服务：在此窗口按 Ctrl+C，必要时回答 Y。
echo.
%PYTHON_CMD% "launcher.py"
set "PAPERSHELF_RC=%errorlevel%"
if not "%PAPERSHELF_RC%"=="0" (
    echo.
    echo 启动失败（错误码 %PAPERSHELF_RC%）。请查看上面的提示。
    pause
)
popd
exit /b %PAPERSHELF_RC%
