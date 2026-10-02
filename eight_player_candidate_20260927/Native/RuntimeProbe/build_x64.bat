@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_runtime_probe.cpp /Fe:ep_runtime_probe.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_runtime_probe.cpp ep_runtime_probe_test.cpp /link /out:ep_runtime_probe_test.exe
if errorlevel 1 goto :fail
ep_runtime_probe_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
