@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
set "SOURCES=ep_player_creation_gate.cpp ep_player_creation_replication_adapter.cpp ..\ClientReplication\ep_replication_bridge.cpp ..\ClientReplication\ep_client_replication_contract.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp"
set "RESOURCE_SOURCES=..\PlayerResource\ep_player_resource.cpp ..\PlayerResource\ep_resource_bridge_adapter.cpp"
cl /nologo /std:c++20 /O2 /EHsc /MT /LD %SOURCES% /Fe:ep_player_creation_gate.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT %SOURCES% ep_player_creation_gate_test.cpp /Fe:ep_player_creation_gate_test.exe
if errorlevel 1 goto :fail
ep_player_creation_gate_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT %SOURCES% ep_player_creation_replication_adapter_test.cpp /Fe:ep_player_creation_replication_adapter_test.exe
if errorlevel 1 goto :fail
ep_player_creation_replication_adapter_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT %SOURCES% %RESOURCE_SOURCES% ep_player_creation_resource_integration_test.cpp /Fe:ep_player_creation_resource_integration_test.exe
if errorlevel 1 goto :fail
ep_player_creation_resource_integration_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
