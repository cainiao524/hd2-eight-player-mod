@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_eight_preflight.cpp /Fe:ep_eight_preflight.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_eight_preflight.cpp ep_eight_preflight_test.cpp /link /out:ep_eight_preflight_test.exe
if errorlevel 1 goto :fail
ep_eight_preflight_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
