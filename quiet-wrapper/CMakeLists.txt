cmake_minimum_required(VERSION 3.10)
project(quiet_simple C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Build as shared library (DLL on Windows)
add_library(quiet_simple SHARED
    quiet_simple.c
    quiet_simple.h
)

target_compile_definitions(quiet_simple PRIVATE QUIET_SIMPLE_BUILD)

# Find quiet headers and library
find_path(QUIET_INCLUDE_DIR quiet.h)
find_library(QUIET_LIBRARY quiet)
if(NOT QUIET_INCLUDE_DIR OR NOT QUIET_LIBRARY)
    message(FATAL_ERROR "Could not find libquiet. Run build_deps.sh first.")
endif()

# Find portaudio
find_path(PORTAUDIO_INCLUDE_DIR portaudio.h)
find_library(PORTAUDIO_LIBRARY portaudio)
if(NOT PORTAUDIO_INCLUDE_DIR OR NOT PORTAUDIO_LIBRARY)
    message(FATAL_ERROR "Could not find portaudio. Run build_deps.sh first.")
endif()

target_include_directories(quiet_simple PRIVATE
    ${QUIET_INCLUDE_DIR}
    ${PORTAUDIO_INCLUDE_DIR}
)

target_link_libraries(quiet_simple PRIVATE
    ${QUIET_LIBRARY}
    ${PORTAUDIO_LIBRARY}
    pthread
)

# Avoid "lib" prefix so the DLL is named quiet_simple.dll
set_target_properties(quiet_simple PROPERTIES PREFIX "")
