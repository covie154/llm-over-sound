cmake_minimum_required(VERSION 3.10)
project(ggwave_simple)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find SDL2
set(SDL2_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../ggwave/SDL2/cmake")
find_package(SDL2 REQUIRED)

# Include ggwave
set(GGWAVE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../ggwave")

# Build as shared library (DLL on Windows)
add_library(ggwave_simple SHARED
    ggwave_simple.cpp
    ggwave_simple.h
    ${GGWAVE_DIR}/src/ggwave.cpp
)

target_include_directories(ggwave_simple PRIVATE
    ${GGWAVE_DIR}/include
    ${SDL2_INCLUDE_DIRS}
)

target_link_libraries(ggwave_simple PRIVATE
    ${SDL2_LIBRARIES}
)

target_compile_definitions(ggwave_simple PRIVATE
    GGWAVE_SIMPLE_BUILD
)

# Copy SDL2.dll to output directory on Windows
if(WIN32)
    add_custom_command(TARGET ggwave_simple POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${GGWAVE_DIR}/SDL2/lib/x64/SDL2.dll"
        $<TARGET_FILE_DIR:ggwave_simple>
    )
endif()
