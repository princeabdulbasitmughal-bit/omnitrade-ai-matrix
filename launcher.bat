@echo off
title OmniTrade AI Matrix — Multi-Model AI Trading Terminal
cd /d "e:\omnitrade-ai-matrix"
echo =================================================================
echo   OMNITRADE AI MATRIX — QUANTUM OPEN-SOURCE AI TRADING BOT
echo   Compute Node: NVIDIA RTX A6000 (48GB VRAM)
echo   Swarm: Qwen 32B | DeepSeek 16B | Kimi K3 | Llama 3.3 70B
echo =================================================================
echo.
python -X utf8 run_bot.py
pause
