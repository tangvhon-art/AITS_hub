@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  AITS 前端启动脚本 (Windows)
REM  用法: start_frontend.bat [--port PORT] [--build]
REM ============================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "FRONTEND_DIR=%SCRIPT_DIR%\frontend"
set "PORT=5173"
set "MODE=dev"

REM ---- 参数解析 ----
:parse
if "%~1"=="" goto endparse
if /i "%~1"=="--port" (set "PORT=%~2" & shift)
if /i "%~1"=="--build" set "MODE=build"
shift
goto parse
:endparse

cd /d "%FRONTEND_DIR%"

REM ---- 安装依赖 ----
if not exist "node_modules" (
    echo [前端] 安装 Node.js 依赖...
    call npm install
    if errorlevel 1 (
        echo [前端] [错误] npm install 失败，请检查 Node.js / 网络
        pause
        exit /b 1
    )
)

REM ---- 启动 ----
if /i "%MODE%"=="build" (
    echo [前端] 构建生产版本...
    call npm run build
    if errorlevel 1 (
        echo [前端] [错误] 构建失败
        pause
        exit /b 1
    )
    echo [前端] 构建完成，输出目录: dist\
    echo [前端] 预览地址: http://localhost:%PORT%
    call npm run preview -- --port %PORT% --host 0.0.0.0
) else (
    echo [前端] 启动开发服务器 (port=%PORT%)
    echo [前端] 访问地址: http://localhost:%PORT%
    echo -----------------------------------------------------------
    call npm run dev -- --port %PORT% --host 0.0.0.0
)
pause
