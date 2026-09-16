@echo off
chcp 65001 >nul
title 聆语智服 · 服务端
echo ============================================
echo  聆语智服 LingYu · 服务端启动
echo  Swagger:  http://127.0.0.1:3001/docs
echo  环境自检:  http://127.0.0.1:3001/api/env-check
echo ============================================
cd /d %~dp0server
python run.py
pause
