cmake_minimum_required(VERSION 3.18)
set(CMAKE_CXX_STANDARD 20)
project(ProductAutomata VERSION 0.1.0 LANGUAGES C CXX)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}")

add_executable(ProductAutomata main.cpp RegPDFA.cpp urgf.cpp)

#find_package(mp++ REQUIRED)
#target_link_libraries(ProductAutomata mp++::mp++)
find_package(mgl)
target_link_libraries(ProductAutomata ${MathGL_LIBRARIES})
find_package(FLINT REQUIRED)
target_link_libraries(ProductAutomata ${FLINT_LIBRARIES})
target_include_directories(ProductAutomata PUBLIC ${FLINT_INCLUDE_DIR})