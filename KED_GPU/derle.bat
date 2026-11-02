@echo off
rem ked_cekirdek.c -> ked_cekirdek.dll (Visual Studio 2022 Build Tools ile)
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /LD /W3 ked_cekirdek.c /Fe:ked_cekirdek.dll /link /NOLOGO || exit /b 1
del /q ked_cekirdek.obj ked_cekirdek.lib ked_cekirdek.exp 2>nul
echo DERLENDI: ked_cekirdek.dll
