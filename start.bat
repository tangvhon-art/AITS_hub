@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  AITS 智能测试管理平台 - Windows 一键启动脚本
REM  （对应仓库根目录 start.sh 的 Windows 版本）
REM
REM  用法:
REM    start.bat                                   启动全部（后端+前端+Celery+Flower）
REM    start.bat stop                              停止全部服务
REM    start.bat --backend-only                    仅启动后端+Celery
REM    start.bat --frontend-only                   仅启动前端
REM    start.bat --no-celery                       不启动 Celery（连带不启动 Flower）
REM    start.bat --no-flower                       不启动 Flower
REM    start.bat --all                             全部启动（默认）
REM    start.bat --port-backend 8000 --port-frontend 5173 --port-flower 5555
REM
REM  说明:
REM    1. 各服务在独立窗口中运行（后端 / 前端 / Redis / 4个Celery Worker / Beat / Flower），
REM       关闭主窗口不会停止它们，请运行 start.bat stop 停止。
REM    2. 首次运行会自动创建 backend\venv（Windows 版）并安装依赖；
REM       如果 backend\venv 是从 Mac/Linux 复制来的（只有 bin 目录），请先删除再运行本脚本。
REM    3. Celery 在 Windows 下无法使用 prefork 池（无 fork），本脚本使用 threads 线程池，
REM       如需与 macOS 一致可改用 eventlet（已在 requirements.txt 中）: -P eventlet -c 2
REM ============================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%SCRIPT_DIR%\backend"
set "VENV=%BACKEND_DIR%\venv\Scripts\python.exe"

set "ACTION=start"
set "START_BACKEND=1"
set "START_FRONTEND=1"
set "START_CELERY=1"
set "START_FLOWER=1"
set "PORT_BACKEND=8000"
set "PORT_FRONTEND=5173"
set "PORT_FLOWER=5555"

REM ---- 参数解析 ----
:parse
if "%~1"=="" goto endparse
if /i "%~1"=="stop"                    set "ACTION=stop"
if /i "%~1"=="--help"                  goto usage
if /i "%~1"=="--backend-only"          set "START_FRONTEND=0"
if /i "%~1"=="--frontend-only"         set "START_BACKEND=0"
if /i "%~1"=="--no-celery"             (set "START_CELERY=0" & set "START_FLOWER=0")
if /i "%~1"=="--no-flower"             set "START_FLOWER=0"
if /i "%~1"=="--all"                   (set "START_CELERY=1" & set "START_FLOWER=1")
if /i "%~1"=="--port-backend"          (set "PORT_BACKEND=%~2" & shift)
if /i "%~1"=="--port-frontend"         (set "PORT_FRONTEND=%~2" & shift)
if /i "%~1"=="--port-flower"           (set "PORT_FLOWER=%~2" & shift)
shift
goto parse
:endparse

REM ---- 停止入口 ----
if /i "%ACTION%"=="stop" (
    echo    停止所有 AITS 服务...
    call :stop_all
    echo    已停止
    exit /b 0
)

echo ============================================
echo   AITS 智能测试管理平台 - 启动中
echo ============================================
echo.

REM ---- 启动前清理，避免端口冲突和重复 worker ----
echo    检查并停止已有 AITS 进程...
call :stop_all

REM ---- 确保后端 venv 已就绪（避免与后端窗口并发创建产生竞态）----
if "%START_BACKEND%"=="1" call :ensure_venv
if "%START_CELERY%"=="1" call :ensure_venv

REM ---- Redis（Celery 依赖）----
if "%START_CELERY%"=="1" call :ensure_redis

REM ---- 后端 ----
if "%START_BACKEND%"=="1" (
    echo    启动后端 (port=%PORT_BACKEND%)...
    start "AITS Backend" cmd /c ""%SCRIPT_DIR%\start_backend.bat" --port %PORT_BACKEND%"
)

REM ---- 前端 ----
if "%START_FRONTEND%"=="1" (
    echo    启动前端 (port=%PORT_FRONTEND%)...
    start "AITS Frontend" cmd /c ""%SCRIPT_DIR%\start_frontend.bat" --port %PORT_FRONTEND%"
)

REM ---- Celery Worker + Beat ----
if "%START_CELERY%"=="1" call :start_celery

REM ---- Flower 监控面板 ----
if "%START_FLOWER%"=="1" call :start_flower

echo.
echo 服务已启动:
if "%START_BACKEND%"=="1"  echo   后端 API:   http://localhost:%PORT_BACKEND%
if "%START_BACKEND%"=="1"  echo   API 文档:   http://localhost:%PORT_BACKEND%/docs
if "%START_FRONTEND%"=="1" echo   前端页面:   http://localhost:%PORT_FRONTEND%
if "%START_CELERY%"=="1" (
    echo   Celery:    4 个队列已启动（ai / execution / default / eval, threads 线程池 并发=2）
    echo   Beat:      定时任务调度器已启动
)
if "%START_FLOWER%"=="1" echo   Flower:    http://localhost:%PORT_FLOWER%/flower/
echo.
echo 日志文件: logs\worker-ai.log / worker-execution.log / worker-default.log / worker-eval.log / beat.log / flower.log
echo.
echo 按任意键停止全部服务（或另开终端运行 start.bat stop）...
pause >nul
call :stop_all
echo 已停止
exit /b 0

REM ============================================================
REM  子过程
REM ============================================================

:ensure_venv
if exist "%VENV%" (
    if exist "%BACKEND_DIR%\venv\.deps_installed" exit /b 0
    echo    检测到 venv 但依赖未安装，先在主窗口安装依赖...
    cd /d "%BACKEND_DIR%"
    "%VENV%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo    [警告] 依赖安装失败，请检查网络或 requirements.txt
    ) else (
        echo done> "%BACKEND_DIR%\venv\.deps_installed"
    )
    exit /b 0
)
echo    未找到后端 Windows 虚拟环境，正在创建 venv\Scripts ...
if not exist "%BACKEND_DIR%\venv" mkdir "%BACKEND_DIR%\venv"
cd /d "%BACKEND_DIR%"
where python >nul 2>&1
if errorlevel 1 (
    echo    [错误] 未找到 python 命令，请先安装 Python 3 并加入 PATH
    pause
    exit /b 1
)
python -m venv venv
if not exist "%VENV%" (
    echo    [错误] venv 创建失败
    pause
    exit /b 1
)
echo    安装 Python 依赖...
"%VENV%" -m pip install --upgrade pip >nul 2>&1
"%VENV%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo    [警告] 依赖安装失败，请检查网络或 requirements.txt
) else (
    echo done> "%BACKEND_DIR%\venv\.deps_installed"
)
exit /b 0

:ensure_redis
set "REDIS_OK="
where redis-cli >nul 2>&1
if not errorlevel 1 (
    redis-cli ping >nul 2>&1 && set "REDIS_OK=1"
)
if defined REDIS_OK (
    echo    Redis 已在运行
    exit /b 0
)
where redis-server >nul 2>&1
if not errorlevel 1 (
    echo    Redis 未运行，启动 redis-server...
    start "AITS Redis" cmd /c "redis-server"
    timeout /t 2 /nobreak >nul
    exit /b 0
)
where docker >nul 2>&1
if not errorlevel 1 (
    echo    redis-cli/redis-server 不可用，尝试用 Docker 启动 Redis (docker compose up -d redis)...
    cd /d "%SCRIPT_DIR%"
    docker compose up -d redis
    if errorlevel 1 (
        echo    [警告] docker compose 启动 Redis 失败，Celery 将无法工作
    ) else (
        echo    Redis 容器已启动
    )
    timeout /t 3 /nobreak >nul
    exit /b 0
)
echo    [警告] 无法启动 Redis（未找到 redis-server / docker），Celery 将无法工作
exit /b 0

:start_celery
echo    启动 Celery 多队列 Worker...
if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"
echo    并发模式: Windows threads 线程池，每队列并发=2
set "POOL_ARG=-P threads"
set "CONC=-c 2"

start "AITS Celery-ai" cmd /c ""cd /d "%BACKEND_DIR%" && set "PYTHONPATH=" && "%VENV%" -m celery -A app.celery_app.celery_app worker --loglevel=info %POOL_ARG% %CONC% --hostname=ai-worker@%COMPUTERNAME% -Q ai --events --heartbeat-interval=5 > "%SCRIPT_DIR%\logs\worker-ai.log" 2>&1"
echo    AI Worker 已启动 (队列=ai, 并发=2) -^> logs\worker-ai.log

start "AITS Celery-execution" cmd /c ""cd /d "%BACKEND_DIR%" && set "PYTHONPATH=" && "%VENV%" -m celery -A app.celery_app.celery_app worker --loglevel=info %POOL_ARG% %CONC% --hostname=execution-worker@%COMPUTERNAME% -Q execution --events --heartbeat-interval=5 > "%SCRIPT_DIR%\logs\worker-execution.log" 2>&1"
echo    Execution Worker 已启动 (队列=execution, 并发=2) -^> logs\worker-execution.log

start "AITS Celery-default" cmd /c ""cd /d "%BACKEND_DIR%" && set "PYTHONPATH=" && "%VENV%" -m celery -A app.celery_app.celery_app worker --loglevel=info %POOL_ARG% %CONC% --hostname=default-worker@%COMPUTERNAME% -Q default --events --heartbeat-interval=5 > "%SCRIPT_DIR%\logs\worker-default.log" 2>&1"
echo    Default Worker 已启动 (队列=default, 并发=2) -^> logs\worker-default.log

start "AITS Celery-eval" cmd /c ""cd /d "%BACKEND_DIR%" && set "PYTHONPATH=" && "%VENV%" -m celery -A app.celery_app.celery_app worker --loglevel=info %POOL_ARG% %CONC% --hostname=eval-worker@%COMPUTERNAME% -Q eval --events --heartbeat-interval=5 > "%SCRIPT_DIR%\logs\worker-eval.log" 2>&1"
echo    Eval Worker 已启动 (队列=eval, 并发=2) -^> logs\worker-eval.log

REM Beat 必须单实例运行，--pidfile 防止重复启动
start "AITS Celery-Beat" cmd /c ""cd /d "%BACKEND_DIR%" && set "PYTHONPATH=" && "%VENV%" -m celery -A app.celery_app.celery_app beat --loglevel=info --pidfile="%SCRIPT_DIR%\logs\beat.pid" > "%SCRIPT_DIR%\logs\beat.log" 2>&1"
echo    Beat 调度器 已启动 -^> logs\beat.log

echo    等待 Worker 就绪...
timeout /t 3 /nobreak >nul
set "WORKER_READY="
for /l %%i in (1,1,10) do (
    "%VENV%" -m celery -A app.celery_app.celery_app inspect ping -d "ai-worker@%COMPUTERNAME%" >nul 2>&1 && set "WORKER_READY=1"
    if defined WORKER_READY goto worker_ready
    timeout /t 2 /nobreak >nul
)
echo    [警告] Worker 就绪检测超时（进程可能仍在启动中，可查看 logs\worker-ai.log）
goto worker_done
:worker_ready
echo    所有 Worker 已就绪
:worker_done
exit /b 0

:start_flower
echo    启动 Flower 监控面板 (port=%PORT_FLOWER%)...
if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"
start "AITS Flower" cmd /c ""cd /d "%BACKEND_DIR%" && set FLOWER_UNAUTHENTICATED_API=true && "%VENV%" -m celery -A app.celery_app.celery_app flower --port=%PORT_FLOWER% --conf=flowerconfig.py --auto_refresh=true > "%SCRIPT_DIR%\logs\flower.log" 2>&1"
echo    Flower 已启动: http://localhost:%PORT_FLOWER%/flower/
exit /b 0

:stop_all
powershell -NoProfile -ExecutionPolicy Bypass -Command "$me=$PID; $ports=@(%PORT_BACKEND%,%PORT_FRONTEND%,%PORT_FLOWER%); Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $me -and ($_.CommandLine -match 'celery_app|uvicorn|vite|redis-server') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in $ports } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul
exit /b 0

:usage
echo 用法:
echo   start.bat                                  启动全部（后端+前端+Celery+Flower）
echo   start.bat stop                             停止全部服务
echo   start.bat --backend-only                   仅启动后端+Celery
echo   start.bat --frontend-only                  仅启动前端
echo   start.bat --no-celery                      不启动 Celery（连带不启动 Flower）
echo   start.bat --no-flower                      不启动 Flower
echo   start.bat --all                            全部启动（默认）
echo   start.bat --port-backend 8000 --port-frontend 5173 --port-flower 5555
exit /b 0
