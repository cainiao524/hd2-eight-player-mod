@echo off
setlocal
pushd "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT /LD ep_capacity_patch.cpp /Fe:eight_player_capacity_pluginw64_release.dll
if errorlevel 1 goto :fail
cl /nologo /std:c++20 /O2 /EHsc /MT ep_capacity_patch.cpp capacity_patch_test.cpp /Fe:capacity_patch_test.exe
if errorlevel 1 goto :fail
capacity_patch_test.exe
if errorlevel 1 goto :fail
popd
endlocal
exit /b 0
:fail
set code=%errorlevel%
popd
endlocal & exit /b %code%
