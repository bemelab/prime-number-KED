@echo off
rem ked_cekirdek.c -> ked_cekirdek.dll, LLVM clang ile (-O2).
rem Olcum (7T+100G, 24 isci): -O2 3,35 / -O2 -march=native 3,23 / -O3 3,15 / -O3 -march=native 3,08 milyar sayi/sn.
rem Windows SDK kutuphaneleri icin Visual Studio 2022 Build Tools ortami kullanilir.
rem clang_rt.builtins: 128 bit bolme (__umodti3) icin.
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
"C:\Program Files\LLVM\bin\clang.exe" -O2 -shared -Wall -Wno-unused-function ked_cekirdek.c -o ked_cekirdek.dll "C:\Program Files\LLVM\lib\clang\23\lib\windows\clang_rt.builtins-x86_64.lib" || exit /b 1
del /q ked_cekirdek.lib ked_cekirdek.exp 2>nul
echo DERLENDI: ked_cekirdek.dll (clang)
