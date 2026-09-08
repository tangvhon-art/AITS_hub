@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  AITS 后端启动脚本 (Windows)
REM  用法: start_backend.bat [--no-reload] [--port PORT]
REM ============================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%SCRIPT_DIR%\backend"
set "VENV_DIR=%BACKEND_DIR%\venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PORT=8000"
set "RELOAD=--reload"

REM ---- 参数解析 ----
:parse
if "%~1"=="" goto endparse
if /i "%~1"=="--no-reload" set "RELOAD="
if /i "%~1"=="--port" (set "PORT=%~2" & shift)
shift
goto parse
:endparse

REM ---- 虚拟环境 ----
if not exist "%PY%" (
    echo [后端] 未找到 Windows 虚拟环境，正在创建 venv\Scripts ...
    REM 若 backend\venv 是从 Mac/Linux 复制来的（仅含 bin 目录），建议删除后重新创建
    cd /d "%BACKEND_DIR%"
    where python >nul 2>&1
    if errorlevel 1 (
        echo [后端] [错误] 未找到 python 命令，请先安装 Python 3 并加入 PATH
        pause
        exit /b 1
    )
    python -m venv venv
    if not exist "%PY%" (
        echo [后端] [错误] venv 创建失败
        pause
        exit /b 1
    )
    echo [后端] 安装 Python 依赖...
    "%PY%" -m pip install --upgrade pip >nul 2>&1
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [后端] [警告] 依赖安装失败，请检查网络或 requirements.txt
    ) else (
        echo done> "%VENV_DIR%\.deps_installed"
    )
) else (
    if not exist "%VENV_DIR%\.deps_installed" (
        echo [后端] 首次运行，安装 Python 依赖...
        "%PY%" -m pip install -r requirements.txt
        if errorlevel 1 (
            echo [后端] [警告] 依赖安装失败，请检查网络或 requirements.txt
        ) else (
            echo done> "%VENV_DIR%\.deps_installed"
        )
    )
)

REM ---- Playwright Chromium 浏览器（如未安装）----
if not exist "%LOCALAPPDATA%\ms-playwright\chromium*" (
    echo [后端] 安装 Playwright Chromium 浏览器...
    "%PY%" -m playwright install chromium
)

REM ---- 检查并初始化数据库 ----
echo [后端] 检查并初始化数据库...
"%PY%" -c "from app.main import engine, _auto_migrate; from app.models import *; from app.database import Base; Base.metadata.create_all(bind=engine); _auto_migrate(engine); print('数据库初始化完成')" 2>nul
if errorlevel 1 (
    echo [后端] [警告] 数据库初始化失败，将继续启动（运行时会自动重试）
)

REM ---- 启动 uvicorn ----
cd /d "%BACKEND_DIR%"
if defined RELOAD (
    echo [后端] 启动 uvicorn (port=%PORT%, reload=开)
) else (
    echo [后端] 启动 uvicorn (port=%PORT%, reload=关)
)
echo [后端] API 地址: http://localhost:%PORT%
echo [后端] 文档地址: http://localhost:%PORT%/docs
echo -----------------------------------------------------------
"%PY%" -m uvicorn app.main:app %RELOAD% --host 0.0.0.0 --port %PORT%
pause
