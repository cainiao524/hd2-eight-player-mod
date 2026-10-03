@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ..\Sidecar\ep_sidecar.cpp ep_native_bridge.cpp /Fe:ep_native_bridge.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ..\Sidecar\ep_sidecar.cpp ep_native_bridge.cpp ep_native_bridge_test.cpp /link /out:ep_native_bridge_test.exe
if errorlevel 1 goto :fail
ep_native_bridge_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ..\Sidecar\ep_sidecar.cpp ep_native_bridge.cpp ..\ClientSidecar\ep_client_sidecar.cpp ..\ClientSidecar\ep_client_bridge_adapter.cpp ep_bridge_client_integration_test.cpp /link /out:ep_bridge_client_integration_test.exe
if errorlevel 1 goto :fail
ep_bridge_client_integration_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
