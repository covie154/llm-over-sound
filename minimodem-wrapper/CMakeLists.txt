cmake_minimum_required(VERSION 3.10)
project(minimodem_simple C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Source layout
#   mm_core.c            : minimodem.c main() TX/RX loops decomposed into a
#                          context-struct library (Plan 07-01 Task 2)
#   simpleaudio-winmm.c  : WinMM audio backend (Plan 07-01 Task 3, Windows)
#   minimodem_simple.c   : public API + RX thread + queue (Plan 07-02)
#   vendor/*.c           : vendored minimodem core DSP sources
# ---------------------------------------------------------------------------

set(MM_VENDOR_SOURCES
    vendor/fsk.c
    vendor/simple-tone-generator.c
    vendor/databits_ascii.c
    vendor/simpleaudio.c
)

set(MM_CORE_SOURCES
    mm_core.c
)

# minimodem_simple.c (public API + RX thread) is authored in Plan 07-02.
# Include it in the library build only once it exists so Plan 07-01 can build
# the decomposed core + WinMM backend on its own.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/minimodem_simple.c")
    list(APPEND MM_CORE_SOURCES minimodem_simple.c)
endif()

if(WIN32)
    set(MM_BACKEND_SOURCES simpleaudio-winmm.c)
else()
    set(MM_BACKEND_SOURCES vendor/simpleaudio-alsa.c vendor/simpleaudio-pulse.c)
endif()

add_library(minimodem_simple SHARED
    ${MM_CORE_SOURCES}
    ${MM_BACKEND_SOURCES}
    ${MM_VENDOR_SOURCES}
    minimodem_simple.h
)

target_include_directories(minimodem_simple PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/vendor
)

# Avoid the "lib" prefix so the artifact is minimodem_simple.dll / .so name kept clean
set_target_properties(minimodem_simple PROPERTIES PREFIX "")

# CRITICAL (Plan 07-02): the vendored simple-tone-generator.c emits the actual
# audio write INSIDE an assert():
#     assert( simpleaudio_write(sa_out, buf, nsamples_dur) > 0 );
# Upstream minimodem never builds with -DNDEBUG, so this side effect is always
# present. A Release build defines NDEBUG, which strips the assert AND its
# write() call -> TX silently emits NOTHING. Force NDEBUG off for every config so
# the load-bearing assert side effects survive. (Vendored source kept verbatim
# per 07-01; the fix lives in the build, not the upstream file.)
target_compile_options(minimodem_simple PRIVATE -UNDEBUG)

# ---------------------------------------------------------------------------
# Platform-specific deps
# ---------------------------------------------------------------------------
if(WIN32)
    # Windows: self-contained DLL. Static fftw3f + static MinGW runtime so the
    # only runtime deps are Windows system DLLs (winmm, kernel32, msvcrt, ...).
    target_compile_definitions(minimodem_simple PRIVATE
        MINIMODEM_SIMPLE_BUILD
        USE_WINAUDIO
    )

    # MinGW's <strings.h> does not declare bzero (a BSD/glibc-ism used by the
    # vendored fsk.c / simple-tone-generator.c). Force-include a compat shim so
    # the upstream sources compile verbatim without edits.
    target_compile_options(minimodem_simple PRIVATE
        -include "${CMAKE_CURRENT_SOURCE_DIR}/vendor/mm_strings_compat.h")

    # Locate static fftw3f (MSYS2 MinGW64 ships /mingw64/lib/libfftw3f.a).
    find_library(FFTW3F_STATIC_LIB
        NAMES libfftw3f.a fftw3f
        PATHS /mingw64/lib /c/msys64/mingw64/lib
    )
    if(NOT FFTW3F_STATIC_LIB)
        message(FATAL_ERROR
            "Could not find static libfftw3f.a. Run build_deps.sh first "
            "(pacman -S mingw-w64-x86_64-fftw), or build fftw3f from source "
            "with --enable-single --enable-static --disable-shared.")
    endif()
    find_path(FFTW3_INCLUDE_DIR fftw3.h
        PATHS /mingw64/include /c/msys64/mingw64/include)
    if(FFTW3_INCLUDE_DIR)
        target_include_directories(minimodem_simple PRIVATE ${FFTW3_INCLUDE_DIR})
    endif()

    target_link_options(minimodem_simple PRIVATE
        -static -static-libgcc -static-libstdc++)

    target_link_libraries(minimodem_simple PRIVATE
        ${FFTW3F_STATIC_LIB}
        winmm)
else()
    # Linux/Pi: dynamic fftw3f + ALSA/PulseAudio is fine (always present via apt).
    target_compile_definitions(minimodem_simple PRIVATE
        MINIMODEM_SIMPLE_BUILD
        USE_ALSA
        USE_PULSEAUDIO
    )

    find_library(FFTW3F_LIB NAMES fftw3f REQUIRED)
    find_library(ASOUND_LIB NAMES asound)
    find_library(PULSE_SIMPLE_LIB NAMES pulse-simple)
    find_library(PULSE_LIB NAMES pulse)

    target_link_libraries(minimodem_simple PRIVATE ${FFTW3F_LIB} pthread m)
    if(ASOUND_LIB)
        target_link_libraries(minimodem_simple PRIVATE ${ASOUND_LIB})
    endif()
    if(PULSE_SIMPLE_LIB AND PULSE_LIB)
        target_link_libraries(minimodem_simple PRIVATE ${PULSE_SIMPLE_LIB} ${PULSE_LIB})
    endif()
endif()

# ---------------------------------------------------------------------------
# Optional loopback test harness (sources authored in Plan 07-02).
# Wired here now so the CMake target exists; only built once the source lands.
# ---------------------------------------------------------------------------
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/test/loopback_test.c")
    # The loopback test drives the engine directly (mm_build_config / mm_tx_bytes
    # / mm_rx_step / simpleaudio_*), which are INTERNAL symbols not exported from
    # the DLL. So compile the core + vendored DSP straight into the exe (its own
    # in-memory simpleaudio backend replaces the WinMM/ALSA device backend).
    # The test only needs the mm_core engine + DSP + its own in-memory backend;
    # exclude minimodem_simple.c (pthread + device backend) from the exe.
    add_executable(minimodem_loopback
        test/loopback_test.c
        mm_core.c
        ${MM_VENDOR_SOURCES})

    target_include_directories(minimodem_loopback PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/vendor)
    target_compile_definitions(minimodem_loopback PRIVATE MINIMODEM_SIMPLE_BUILD)
    # Same NDEBUG hazard as the DLL: the vendored tone generator writes audio
    # inside an assert(). Keep asserts live so TX actually emits samples.
    target_compile_options(minimodem_loopback PRIVATE -UNDEBUG)

    if(WIN32)
        target_compile_options(minimodem_loopback PRIVATE
            -include "${CMAKE_CURRENT_SOURCE_DIR}/vendor/mm_strings_compat.h")
        if(FFTW3_INCLUDE_DIR)
            target_include_directories(minimodem_loopback PRIVATE ${FFTW3_INCLUDE_DIR})
        endif()
        target_link_libraries(minimodem_loopback PRIVATE ${FFTW3F_STATIC_LIB})
    else()
        target_link_libraries(minimodem_loopback PRIVATE ${FFTW3F_LIB} m)
    endif()
endif()
