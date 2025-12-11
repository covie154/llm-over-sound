@echo off
REM Build script for ggwave_simple.dll
REM Requires Visual Studio with CMake support

echo Building ggwave_simple.dll...

REM Create build directory
if not exist build mkdir build
cd build

REM Configure with CMake
cmake .. -G "Visual Studio 17 2022" -A x64

REM Build Release version
cmake --build . --config Release

REM Copy DLL to AHK folder
if exist Release\ggwave_simple.dll (
    echo.
    echo Copying DLL to AHK folder...
    copy /Y Release\ggwave_simple.dll ..\..\AHK\
    copy /Y Release\SDL2.dll ..\..\AHK\
    echo.
    echo Build successful!
    echo Files copied to AHK folder.
) else (
    echo.
    echo Build failed! DLL not found.
)

cd ..
pause
