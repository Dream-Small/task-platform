@echo off
chcp 65001 >nul
title 重型装备车间生产任务进度数字化跟踪平台
cd /d "%~dp0"
echo 正在启动生产任务进度跟踪平台...
echo 启动后浏览器会自动打开，请勿关闭本窗口（关闭窗口即退出平台）
echo.
"C:\ProgramData\Anaconda3\python.exe" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause
