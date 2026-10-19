@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT /LD ep_official_plugin.cpp ..\SessionMembers\ep_consumer_executor.cpp ..\SessionMembers\ep_consumer_native_callbacks.cpp ..\CapacityControl\ep_capacity_control.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp ..\ClientReplication\ep_client_replication_contract.cpp ..\ClientReplication\ep_replication_bridge.cpp ..\PlayerResource\ep_player_resource.cpp ..\PlayerResource\ep_resource_bridge_adapter.cpp ..\PlayerCreationGate\ep_player_creation_gate.cpp ..\PlayerCreationGate\ep_player_creation_replication_adapter.cpp /Fe:ep_official_plugin.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT /LD ep_official_plugin.cpp ..\SessionMembers\ep_consumer_executor.cpp ..\SessionMembers\ep_consumer_native_callbacks.cpp ..\CapacityControl\ep_capacity_control.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp ..\ClientReplication\ep_client_replication_contract.cpp ..\ClientReplication\ep_replication_bridge.cpp ..\PlayerResource\ep_player_resource.cpp ..\PlayerResource\ep_resource_bridge_adapter.cpp ..\PlayerCreationGate\ep_player_creation_gate.cpp ..\PlayerCreationGate\ep_player_creation_replication_adapter.cpp /Fe:eight_player_pluginw64_release.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT ep_official_plugin.cpp ..\SessionMembers\ep_consumer_executor.cpp ..\SessionMembers\ep_consumer_native_callbacks.cpp ..\CapacityControl\ep_capacity_control.cpp ..\Bridge\ep_native_bridge.cpp ..\Sidecar\ep_sidecar.cpp ..\CapacityContract\ep_capacity_contract.cpp ..\ClientReplication\ep_client_replication_contract.cpp ..\ClientReplication\ep_replication_bridge.cpp ..\PlayerResource\ep_player_resource.cpp ..\PlayerResource\ep_resource_bridge_adapter.cpp ..\PlayerCreationGate\ep_player_creation_gate.cpp ..\PlayerCreationGate\ep_player_creation_replication_adapter.cpp ep_official_plugin_test.cpp /Fe:ep_official_plugin_test.exe
if errorlevel 1 goto :fail
ep_official_plugin_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc ep_official_plugin_load_test.cpp /Fe:ep_official_plugin_load_test.exe
if errorlevel 1 goto :fail
ep_official_plugin_load_test.exe
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT ep_official_session_getter_test.cpp /Fe:ep_official_session_getter_test.exe
if errorlevel 1 goto :fail
ep_official_session_getter_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set "code=%errorlevel%"
popd
endlocal & exit /b %code%
