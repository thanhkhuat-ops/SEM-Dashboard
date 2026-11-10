@echo off
rem Chạy ETL hằng ngày (Task Scheduler "SaleSappV2 ETL daily", 20:30), xong thì gửi tóm tắt cho PIC qua Google Chat
rem (chỉ khi NOTIFY_ENABLED=true trong .env). Log ghi nối vào logs\etl_daily.log
chcp 65001 >nul
cd /d "%~dp0.."
if not exist logs mkdir logs
echo ===== %date% %time% bat dau ===== >> logs\etl_daily.log
".venv\Scripts\python.exe" -m etl.run >> logs\etl_daily.log 2>&1
set ETL_EXIT=%errorlevel%
echo ===== %date% %time% ETL ket thuc, exit code %ETL_EXIT% ===== >> logs\etl_daily.log
if not "%ETL_EXIT%"=="0" exit /b %ETL_EXIT%
".venv\Scripts\python.exe" -m app.notify.run >> logs\etl_daily.log 2>&1
set NOTIFY_EXIT=%errorlevel%
echo ===== %date% %time% gui tin PIC ket thuc, exit code %NOTIFY_EXIT% ===== >> logs\etl_daily.log
exit /b %NOTIFY_EXIT%
