find_path(FLINT_INCLUDE_DIR NAMES flint/flint.h 
  PATHS 
  /opt/local/include
  /usr/include
  /usr/local/include
  ../flint/include
  ../flint-build/include
)
find_library(FLINT_LIBRARY NAMES flint
  PATHS
  /opt/local/lib
  /usr/local/lib
  /usr/lib
  ../flint/lib
  ../flint-build/lib)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(FLINT DEFAULT_MSG FLINT_INCLUDE_DIR FLINT_LIBRARY)
if(FLINT_FOUND)
    MESSAGE(STATUS "FLINT found")
    MESSAGE(STATUS "FLINT Include dirs:" ${FLINT_INCLUDE_DIR})
    MESSAGE(STATUS "FLINT Library:" ${FLINT_LIBRARY})
    set(FLINT_LIBRARIES ${FLINT_LIBRARY})
    set(FLINT_INCLUDE_DIRS ${FLINT_INCLUDE_DIR})
    
endif()
