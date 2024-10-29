cmake_minimum_required(VERSION 3.18)
project(ProductAutomata VERSION 0.1.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
# file(
#   DOWNLOAD
#   https://github.com/cpm-cmake/CPM.cmake/releases/download/v0.38.3/CPM.cmake
#   ${CMAKE_CURRENT_BINARY_DIR}/cmake/CPM.cmake
#   EXPECTED_HASH SHA256=cc155ce02e7945e7b8967ddfaff0b050e958a723ef7aad3766d368940cb15494
# )
include(${CMAKE_CURRENT_BINARY_DIR}/cmake/CPM.cmake)
add_definitions(-DCMAKE_EXPORT_COMPILE_COMMANDS=ON)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/lib)

# PackageProject.cmake will be used to make our target installable
CPMAddPackage("gh:TheLartians/PackageProject.cmake@1.9.0")

option(BUILD_SHARED_LIBS "Build shared libraries" NO)
CPMAddPackage("gh:ClausKlein/boost-cmake@1.79.3")

CPMAddPackage("gh:bluescarni/mppp@1.0.4")

add_executable(ProductAutomata main.cpp)
target_include_directories(
  ${PROJECT_NAME} PUBLIC $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
                         $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
target_link_libraries(ProductAutomata PUBLIC Boost::filesystem)
target_link_libraries(ProductAutomata PUBLIC Boost::boost)



# CPMAddPackage(
#     NAME spdlog
#     GITHUB_REPOSITORY gabime/spdlog
#     VERSION 1.7.0)
    
# target_link_libraries(ProductAutomata 
#     spdlog)

# include(CTest)
# enable_testing()

# set(CPACK_PROJECT_NAME ${PROJECT_NAME})
# set(CPACK_PROJECT_VERSION ${PROJECT_VERSION})
# include(CPack)
