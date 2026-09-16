@echo off
cd /d "%~dp0"

echo ============================================
echo   12306 抢票工具 - 首次使用依赖安装
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 python，请先安装 Python 并加入 PATH。
    pause
    exit /b 1
)

echo [1/4] 升级 pip...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [2/4] 安装项目依赖...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120

echo.
echo [3/4] 安装 / 更新 ChromeDriver...
python tools\update_chromedriver.py

echo.
echo [4/4] 验证 selenium...
python -c "import selenium; print('selenium 版本:', selenium.__version__)"

echo.
echo 安装完成。
pause