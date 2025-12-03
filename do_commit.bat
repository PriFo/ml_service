@echo off
chcp 65001 >nul
git add -A
git commit -F COMMIT_MESSAGE.txt
del COMMIT_MESSAGE.txt
del do_commit.bat

