@echo off
rem Keeps the Telegram demo bot running on this PC: restarts it if it stops.
rem Put a shortcut to this file in shell:startup to start it at logon.
cd /d "%~dp0.."
:loop
python -I -X utf8 -c "import sys; sys.path[:0]=['src','../kepil/src']; from moneygate.telegram_bot import main; raise SystemExit(main())" 2>> data\bot.log
echo %date% %time% bot exited, restarting in 10 s >> data\bot.log
timeout /t 10 /nobreak > nul
goto loop