@echo off
REM Windows launcher for the Discord voice bridge.
REM Double-click to run, or point a Task Scheduler "at log on" task at this file.
cd /d "%~dp0"
python voice_bridge.py
REM Keep the window open if it exits so you can read any error.
pause
