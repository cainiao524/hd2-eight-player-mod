@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
if not exist build mkdir build
pushd build
cl /nologo /std:c++20 /O2 /W4 /EHsc /LD ..\ep_capacity_control.cpp ..\..\Bridge\ep_native_bridge.cpp ..\..\Sidecar\ep_sidecar.cpp ..\..\CapacityContract\ep_capacity_contract.cpp /Fe:ep_capacity_control.dll
if errorlevel 1 goto :buildfail
cl /nologo /std:c++20 /O2 /W4 /EHsc /LD ..\ep_capacity_control.cpp ..\..\Bridge\ep_native_bridge.cpp ..\..\Sidecar\ep_sidecar.cpp ..\..\CapacityContract\ep_capacity_contract.cpp ..\test_control_fixture.cpp /Fe:test_control_fixture.dll
if errorlevel 1 goto :buildfail
popd
popd
endlocal
exit /b 0
:buildfail
popd
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
