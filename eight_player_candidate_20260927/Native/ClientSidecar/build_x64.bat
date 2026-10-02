@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_client_sidecar.cpp /Fe:ep_client_sidecar.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_client_sidecar.cpp ep_client_sidecar_test.cpp /link /out:ep_client_sidecar_test.exe
if errorlevel 1 goto :fail
ep_client_sidecar_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_client_sidecar.cpp ep_client_bridge_adapter.cpp /Fe:ep_client_bridge_adapter.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_client_sidecar.cpp ep_client_bridge_adapter.cpp ep_client_bridge_adapter_test.cpp /link /out:ep_client_bridge_adapter_test.exe
if errorlevel 1 goto :fail
ep_client_bridge_adapter_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
