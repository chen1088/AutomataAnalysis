cmake_minimum_required(VERSION 3.18)
set(CMAKE_CXX_STANDARD 17)
project(ProductAutomata VERSION 0.1.0 LANGUAGES C CXX)
include(ExternalProject)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}")
add_executable(ProductAutomata main.cpp)

find_package(GMP)

set(Boost_USE_STATIC_LIBS OFF) 
set(Boost_USE_MULTITHREADED ON)  
set(Boost_USE_STATIC_RUNTIME OFF) 
find_package(Boost 1.83.0 COMPONENTS filesystem boost) 

if(Boost_FOUND)
    include_directories(${Boost_INCLUDE_DIRS}) 
    target_link_libraries(ProductAutomata PUBLIC Boost::filesystem)
    target_link_libraries(ProductAutomata PUBLIC Boost::boost)
endif()

if(GMP_FOUND)
    target_link_libraries(ProductAutomata PUBLIC gmp gmpxx) 
endif()
