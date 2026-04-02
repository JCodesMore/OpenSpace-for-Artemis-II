@echo off
REM Auto-start script for Artemis 2 poller (called by OpenSpace asset)
cd /d "%~dp0.."
python -m poller.poller --output "%~dp0artemis2_live.dat" --archive-dir "%~dp0archive" --log-dir "%~dp0logs"
