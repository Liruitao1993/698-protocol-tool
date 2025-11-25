@echo off
REM DL/T 698.45协议测试系统 - Git推送脚本
REM 当网络连接正常时，运行此脚本推送代码到远程仓库

echo ========================================
echo DL/T 698.45协议测试系统 Git推送
echo ========================================
echo.

echo 正在检查Git状态...
git status
echo.

echo 正在推送master分支...
git push origin master
if %errorlevel% neq 0 (
    echo.
    echo [错误] 推送master分支失败！
    echo 请检查网络连接或GitHub访问权限
    pause
    exit /b 1
)

echo.
echo 正在推送所有标签...
git push origin --tags
if %errorlevel% neq 0 (
    echo.
    echo [警告] 推送标签失败！
    echo 但master分支已成功推送
    pause
    exit /b 1
)

echo.
echo ========================================
echo 推送成功！
echo ========================================
echo.
echo 已推送内容：
echo - master分支最新提交
echo - 所有版本标签
echo.
pause
