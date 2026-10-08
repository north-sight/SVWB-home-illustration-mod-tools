@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 影之诗主界面立绘一键自动化替换工具

set "ROOT=%~dp0"
set "SCRIPT=%ROOT%auto_replace_home.py"

if not exist "%SCRIPT%" (
    echo [ERROR] 核心脚本不存在: "%SCRIPT%"
    pause
    exit /b 1
)

set "INPUT_DIR=%ROOT%input"
if not exist "%INPUT_DIR%" (
    mkdir "%INPUT_DIR%"
)

set "TARGET_ID=%~1"

if "%TARGET_ID%"=="" (
    echo ========================================================
    echo             影之诗主界面立绘一键自动化替换工具
    echo ========================================================
    echo.
    set /p "TARGET_ID=请输入目标立绘编号 (例如 1005): "
)

if "%TARGET_ID%"=="" (
    echo [ERROR] 目标立绘编号不能为空！
    pause
    exit /b 1
)

echo.
echo 即将开始处理: 目标立绘编号 [%TARGET_ID%]
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] 未找到 Python 环境，请确认已安装 Python 并添加到系统 PATH！
        pause
        exit /b 1
    )
    py -3 "%SCRIPT%" "%TARGET_ID%"
) else (
    python "%SCRIPT%" "%TARGET_ID%"
)

set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo ========================================================
    echo [OK] 一键替换已全部完成！成果位于 output 文件夹。
    echo ========================================================
) else (
    echo ========================================================
    echo [ERROR] 替换过程中出现错误，请检查上方日志。
    echo ========================================================
)

echo.
pause
exit /b %EXIT_CODE%
