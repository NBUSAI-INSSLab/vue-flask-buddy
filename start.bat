@echo off
rem ============================================================
rem  高校教师工作台（Vue + Flask）一键启动（Windows）
rem  双击即可运行：自动检查依赖并启动开发模式
rem  访问地址：http://127.0.0.1:5000
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 3.11 及以上版本。
  pause
  exit /b 1
)

python -c "import flask, waitress, pypdf" >nul 2>nul
if errorlevel 1 (
  echo [提示] 首次运行，正在安装依赖...
  python -m pip install -r requirements.txt
)

echo.
echo   高校教师工作台启动中：http://127.0.0.1:5000  （Ctrl+C 退出）
echo.
start "" http://127.0.0.1:5000
python run.py --port 5000
pause
