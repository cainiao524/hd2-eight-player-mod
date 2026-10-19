@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_client_replication_contract.cpp /Fe:ep_client_replication_contract.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_client_replication_contract.cpp ep_client_replication_contract_test.cpp /link /out:ep_client_replication_contract_test.exe
if errorlevel 1 goto :fail
ep_client_replication_contract_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /LD ep_replication_bridge.cpp ep_client_replication_contract.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp /Fe:ep_replication_bridge.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_replication_bridge.cpp ep_client_replication_contract.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp ..\ClientSidecar\ep_client_sidecar.cpp ..\ClientSidecar\ep_client_bridge_adapter.cpp ep_replication_bridge_test.cpp /Fe:ep_replication_bridge_test.exe
if errorlevel 1 goto :fail
ep_replication_bridge_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_replication_bridge.cpp ep_client_replication_contract.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp ..\PlayerResource\ep_player_resource.cpp ..\PlayerResource\ep_resource_bridge_adapter.cpp ep_replication_resource_integration_test.cpp /Fe:ep_replication_resource_integration_test.exe
if errorlevel 1 goto :fail
ep_replication_resource_integration_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
