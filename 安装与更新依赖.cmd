@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "SCRIPT_PATH=%~f0"
set "IS_ADMIN=0"
net session >nul 2>&1 && set "IS_ADMIN=1"

echo ============================================
echo   12306 抢票工具 - 环境检查与依赖安装
echo ============================================
echo.

set "PYTHON_FOUND=0"
set "PYTHON_OK=0"
set "PY_VER="

where python >nul 2>nul
if errorlevel 1 (
    echo [检查] 未检测到 Python
) else (
    set "PYTHON_FOUND=1"
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo [检查] Python 版本：!PY_VER!
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo [检查] Python 版本低于 3.8
    ) else (
        set "PYTHON_OK=1"
        echo [检查] Python 版本符合要求
    )
)

set "CHROME_VERSION="
for /f "tokens=3" %%a in ('reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version 2^>nul ^| findstr "version"') do set "CHROME_VERSION=%%a"
if not defined CHROME_VERSION (
    for /f "tokens=3" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\BLBeacon" /v version 2^>nul ^| findstr "version"') do set "CHROME_VERSION=%%a"
)
if not defined CHROME_VERSION (
    for /f "tokens=3" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon" /v version 2^>nul ^| findstr "version"') do set "CHROME_VERSION=%%a"
)
if defined CHROME_VERSION (
    echo [检查] Chrome 版本：!CHROME_VERSION!
) else (
    echo [检查] 未检测到 Google Chrome
)

echo.

if "!PYTHON_OK!"=="1" (
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
    python -c "import selenium; print('selenium version:', selenium.__version__)"
) else (
    echo [跳过] Python 不可用，跳过依赖安装
)

echo.
echo ============================================
echo   环境检查结果汇总
echo ============================================
echo.

set "NEED_INSTALL=0"

if "!PYTHON_FOUND!"=="0" (
    echo [缺失] Python 未安装
    set "NEED_INSTALL=1"
) else if "!PYTHON_OK!"=="0" (
    echo [过时] Python 版本低于 3.8，建议升级
    set "NEED_INSTALL=1"
) else (
    echo [正常] Python 已安装且版本符合要求
)

if not defined CHROME_VERSION (
    echo [缺失] Google Chrome 未安装
    set "NEED_INSTALL=1"
) else (
    echo [正常] Google Chrome 已安装，版本 !CHROME_VERSION!
)

echo.

if "!NEED_INSTALL!"=="0" (
    echo 环境检查通过，可以开始抢票。
    echo.
    pause
    exit /b 0
)

echo 以下项目需要处理：
if "!PYTHON_FOUND!"=="0" echo   - Python 未安装
if "!PYTHON_OK!"=="0" echo   - Python 版本过时
if not defined CHROME_VERSION echo   - Google Chrome 未安装
echo.
echo 是否尝试自动下载并安装缺失项？(Y/N)
set /p AUTO_INSTALL=
if /i not "!AUTO_INSTALL!"=="Y" (
    echo.
    echo 已跳过自动安装。
    echo Python 下载：https://mirrors.tuna.tsinghua.edu.cn/python/
    echo Chrome 下载：https://www.google.cn/chrome/
    pause
    exit /b 1
)

if "!IS_ADMIN!"=="0" (
    echo.
    echo 正在请求管理员权限...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"!SCRIPT_PATH!\"\"' -Verb RunAs"
    exit /b
)

echo.
echo ============================================
echo   自动安装缺失项（管理员权限）
echo ============================================
echo.

if "!PYTHON_OK!"=="0" (
    echo [安装] 正在获取最新 Python 版本号...
    set "PY_VER_NEW="
    for /f "delims=" %%v in ('powershell -Command "try { (Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/' -UseBasicParsing -TimeoutSec 10).Content | Select-String -Pattern '3\.\d+\.\d+/' -AllMatches | ForEach-Object { $_.Matches } | ForEach-Object { $_.Value.TrimEnd('/') } | Sort-Object { [version]$_ } -Descending | Select-Object -First 1 } catch { }"') do set "PY_VER_NEW=%%v"

    if "!PY_VER_NEW!"=="" (
        echo [警告] 无法获取最新版本号，使用默认版本 3.12.7
        set "PY_VER_NEW=3.12.7"
    )

    echo [安装] 最新 Python 版本：!PY_VER_NEW!
    echo [安装] 正在从清华镜像下载...
    set "PY_FILE=%TEMP%\python_installer.exe"

    set "PY_URL=https://mirrors.tuna.tsinghua.edu.cn/python/!PY_VER_NEW!/python-!PY_VER_NEW!-amd64.exe"
    echo [下载] !PY_URL!
    powershell -Command "try { Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_FILE!' -UseBasicParsing -TimeoutSec 300 } catch { Write-Host '下载失败: ' + $_.Exception.Message }"

    if exist "!PY_FILE!" (
        echo [安装] 正在静默安装 Python !PY_VER_NEW!...
        "!PY_FILE!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        del "!PY_FILE!"
        echo [完成] Python 安装完成
        set "PYTHON_JUST_INSTALLED=1"
    ) else (
        echo [失败] Python 下载失败，请手动安装
        echo         下载地址：https://mirrors.tuna.tsinghua.edu.cn/python/
    )
)

if not defined CHROME_VERSION (
    echo.
    echo [安装] 正在从 Google 官方 CDN 下载 Chrome...
    set "CHROME_URL=https://dl.google.com/dl/chrome/install/googlechromestandaloneenterprise64.msi"
    set "CHROME_FILE=%TEMP%\chrome_installer.msi"
    powershell -Command "try { Invoke-WebRequest -Uri '!CHROME_URL!' -OutFile '!CHROME_FILE!' -UseBasicParsing -TimeoutSec 600 } catch { Write-Host '下载失败: ' + $_.Exception.Message }"

    if exist "!CHROME_FILE!" (
        echo [安装] 正在静默安装 Chrome...
        msiexec /i "!CHROME_FILE!" /qn /norestart
        del "!CHROME_FILE!"
        echo [完成] Chrome 安装完成
        set "CHROME_JUST_INSTALLED=1"
    ) else (
        echo [失败] Chrome 下载失败，请手动安装
        echo         下载地址：https://www.google.cn/chrome/
    )
)

if defined PYTHON_JUST_INSTALLED (
    echo.
    echo ============================================
    echo   正在刷新环境变量...
    echo ============================================
    echo.

    set "SYS_PATH="
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"

    set "USER_PATH="
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"

    if defined USER_PATH (
        set "PATH=!USER_PATH!;!SYS_PATH!"
    ) else (
        set "PATH=!SYS_PATH!"
    )

    echo 环境变量已刷新。
    echo 正在重新运行安装脚本...
    echo.
    timeout /t 2 /nobreak >nul

    start "" cmd /c ""!SCRIPT_PATH!""
    exit /b 0
)

echo.
echo ============================================
echo   安装完成
echo ============================================
echo.
echo 请关闭此窗口，重新运行「安装与更新依赖.cmd」以完成依赖安装。
echo.
pause