cmake_minimum_required(VERSION 3.18)
project(ProductAutomata VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}")

add_executable(ProductAutomata main.cpp RegPDFA.cpp)
add_executable(MatM mm.cpp RegPDFA.cpp)

add_library(ProductAutomataDeps INTERFACE)

find_package(flint CONFIG QUIET)
if(TARGET flint::flint)
    message(STATUS "Using FLINT package config target flint::flint")
    target_link_libraries(ProductAutomataDeps INTERFACE flint::flint)
else()
    message(STATUS "Using legacy FindFLINT/FindGMP modules")
    find_package(GMP REQUIRED)
    find_package(FLINT REQUIRED)
    target_link_libraries(ProductAutomataDeps INTERFACE ${FLINT_LIBRARIES} ${GMP_LIBRARIES})
    target_include_directories(ProductAutomataDeps INTERFACE
        ${FLINT_INCLUDE_DIRS}
        ${FLINT_INCLUDE_DIR}
        ${GMP_INCLUDES}
    )
endif()

target_link_libraries(ProductAutomata PRIVATE ProductAutomataDeps)
target_link_libraries(MatM PRIVATE ProductAutomataDeps)
