@echo off
chcp 65001 >nul
title 聆语智服 · 前端
echo ============================================
echo  聆语智服 LingYu · 前端启动
echo  浏览器打开: http://127.0.0.1:5173
echo ============================================
cd /d %~dp0web
if not exist node_modules (
  echo 首次运行，正在安装依赖，请稍候...
  call npm install --legacy-peer-deps
)
npm run dev
pause
