cmake_minimum_required(VERSION 3.16)
project(minimodem_simple C)

set(CMAKE_C_STANDARD 99)

add_library(minimodem_simple SHARED
    minimodem_simple.c
    minimodem_simple.h
    fsk.c
    fsk.h
    tone_generator.c
    tone_generator.h
    databits_ascii.c
    databits.h
)

target_compile_definitions(minimodem_simple PRIVATE MINIMODEM_SIMPLE_BUILD)

# FFTW3f (single-precision float FFT)
find_library(FFTW3F_LIB NAMES fftw3f libfftw3f-3)
find_path(FFTW3F_INCLUDE fftw3.h)

# PortAudio
find_library(PORTAUDIO_LIB NAMES portaudio libportaudio-2)
find_path(PORTAUDIO_INCLUDE portaudio.h)

target_include_directories(minimodem_simple PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FFTW3F_INCLUDE}
    ${PORTAUDIO_INCLUDE}
)

target_link_libraries(minimodem_simple PRIVATE
    ${FFTW3F_LIB}
    ${PORTAUDIO_LIB}
    pthread
    m
)

# Static-link MinGW runtime for portability
if(MINGW)
    target_link_options(minimodem_simple PRIVATE -static-libgcc)
endif()

set_target_properties(minimodem_simple PROPERTIES PREFIX "")
