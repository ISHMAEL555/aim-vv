cmake_minimum_required(VERSION 3.16)
project(aim C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(aim SHARED
    src/decoder.c
    src/monitor.c
    src/alerter.c
    src/aim.c
)

target_include_directories(aim PUBLIC src)

target_compile_options(aim PRIVATE -Wall -Wextra -Werror)

# UART frame parser for the Phase 7 target; built as its own shared library
# so the host tests can exercise exactly the code the firmware compiles.
add_library(aimframer SHARED target/aim_target/framer.c)
target_include_directories(aimframer PUBLIC target/aim_target)
target_compile_options(aimframer PRIVATE -Wall -Wextra -Werror)

option(AIM_COVERAGE "Build with gcov instrumentation (-O0, branch coverage)" OFF)
if(AIM_COVERAGE)
    target_compile_options(aim PRIVATE --coverage -O0 -g)
    target_link_options(aim PRIVATE --coverage)
    target_compile_options(aimframer PRIVATE --coverage -O0 -g)
    target_link_options(aimframer PRIVATE --coverage)
endif()

option(AIM_STRICT "Extra warnings for static-analysis builds" OFF)
if(AIM_STRICT)
    target_compile_options(aimframer PRIVATE -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes
                                             -Wmissing-prototypes -Wundef -Wswitch-enum -pedantic)
    target_compile_options(aim PRIVATE -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes
                                       -Wmissing-prototypes -Wundef -Wswitch-enum -pedantic)
endif()
