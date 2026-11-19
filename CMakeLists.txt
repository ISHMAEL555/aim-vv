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
