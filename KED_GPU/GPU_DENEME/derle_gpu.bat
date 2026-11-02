@echo off
rem gpu_deneme.c -> gpu_deneme.exe (Visual Studio 2022 Build Tools; OpenCL.dll calisma aninda yuklenir)
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /openmp:llvm /W3 /TP gpu_deneme.c /Fe:gpu_deneme.exe /link /NOLOGO || exit /b 1
del /q gpu_deneme.obj 2>nul
echo DERLENDI: gpu_deneme.exe

