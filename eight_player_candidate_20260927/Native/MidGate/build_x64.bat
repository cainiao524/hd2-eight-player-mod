@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT /LD ep_midgate_executor.cpp /Fe:ep_midgate_executor.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT ep_midgate_executor.cpp ep_midgate_executor_test.cpp /Fe:ep_midgate_executor_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT ep_midgate_executor_load_test.cpp /Fe:ep_midgate_executor_load_test.exe
if errorlevel 1 goto :fail
ep_midgate_executor_test.exe
if errorlevel 1 goto :fail
ep_midgate_executor_load_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
