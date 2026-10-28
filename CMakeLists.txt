cmake_minimum_required(VERSION 3.18)
project(ProductAutomata VERSION 0.1.0 LANGUAGES C CXX)

if(CMAKE_TOOLCHAIN_FILE)
    message(STATUS "Using toolchain file: ${CMAKE_TOOLCHAIN_FILE}")
endif()

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# This standard-library-only executable is deliberately separate from the
# legacy algebra experiments and the SAT targets. A dedicated offline build
# never enters dependency discovery or vcpkg manifest installation.
option(FAMILY1_OFFLINE_ONLY "Build only the dependency-free Family1 executables" OFF)
add_library(Family1OfflineCore STATIC Family1LargeGraph.cpp Family1LargeEnumerator.cpp
    Family1ExactPacked.cpp Family1EditSearch.cpp)
target_include_directories(Family1OfflineCore PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(Family1Offline family1_offline.cpp)
target_link_libraries(Family1Offline PRIVATE Family1OfflineCore)
add_executable(Family1Joint family1_joint.cpp)
target_link_libraries(Family1Joint PRIVATE Family1OfflineCore)
add_executable(Family1NearPair family1_near.cpp)
target_link_libraries(Family1NearPair PRIVATE Family1OfflineCore)
add_executable(Family1Certified family1_certified.cpp Family1Certified.cpp Family1Signatures.cpp)
target_link_libraries(Family1Certified PRIVATE Family1OfflineCore)
set(FAMILY1_CERTIFIED_COMPILE_FINGERPRINT "")
foreach(FAMILY1_CERTIFIED_SOURCE IN ITEMS family1_certified.cpp Family1Certified.h Family1Certified.cpp
        Family1Signatures.h Family1Signatures.cpp Family1CertifiedHeuristic.h HardPairJointFinder.h
        Family1CliArtifacts.h Family1LargeGraph.h Family1LargeGraph.cpp)
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_CERTIFIED_SOURCE}" FAMILY1_CERTIFIED_FILE_SHA256)
    string(APPEND FAMILY1_CERTIFIED_COMPILE_FINGERPRINT "${FAMILY1_CERTIFIED_FILE_SHA256}\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_CERTIFIED_SOURCE}")
endforeach()
string(SHA256 FAMILY1_CERTIFIED_SOURCE_SHA256 "${FAMILY1_CERTIFIED_COMPILE_FINGERPRINT}")
target_compile_definitions(Family1Certified PRIVATE FAMILY1_CERTIFIED_SOURCE_SHA256="${FAMILY1_CERTIFIED_SOURCE_SHA256}")
set(FAMILY1_NEAR_COMPILE_SOURCES family1_near.cpp Family1NearPair.h Family1ScoredSeeds.h
    Family1JointPair.h Family1JointSeeds.h HardPairJointFinder.h HardPairPrefixSeeds.h
    Family1ExactPacked.h Family1ExactPacked.cpp Family1LargeGraph.h Family1LargeGraph.cpp
    Family1PairAgreement.h Family1CliArtifacts.h Family1TailScoredSeeds.h HardPairViability.h)
set(FAMILY1_NEAR_COMPILE_FINGERPRINT "")
foreach(FAMILY1_NEAR_SOURCE IN LISTS FAMILY1_NEAR_COMPILE_SOURCES)
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_NEAR_SOURCE}" FAMILY1_NEAR_FILE_SHA256)
    string(APPEND FAMILY1_NEAR_COMPILE_FINGERPRINT "${FAMILY1_NEAR_FILE_SHA256}\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_NEAR_SOURCE}")
endforeach()
string(SHA256 FAMILY1_NEAR_SOURCE_SHA256 "${FAMILY1_NEAR_COMPILE_FINGERPRINT}")
target_compile_definitions(Family1NearPair PRIVATE FAMILY1_NEAR_SOURCE_SHA256="${FAMILY1_NEAR_SOURCE_SHA256}")
if(MSVC)
    set_property(TARGET Family1OfflineCore Family1Offline Family1Joint Family1NearPair Family1Certified PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    set_target_properties(Family1OfflineCore Family1Offline Family1Joint Family1NearPair Family1Certified PROPERTIES
        VS_GLOBAL_VcpkgEnabled "false" VS_GLOBAL_VcpkgEnableManifest "false")
endif()
install(TARGETS Family1Offline Family1Joint Family1NearPair Family1Certified RUNTIME DESTINATION .)
include(CTest)
if(BUILD_TESTING)
    add_test(NAME family1-offline-help COMMAND Family1Offline --help)
    add_test(NAME family1-joint-help COMMAND Family1Joint --help)
    add_test(NAME family1-near-help COMMAND Family1NearPair --help)
    add_test(NAME family1-certified-help COMMAND Family1Certified --help)
    add_executable(Family1NearPairIndependent tests/Family1NearPairIndependent.cpp)
    target_link_libraries(Family1NearPairIndependent PRIVATE Family1OfflineCore)
    add_test(NAME family1-near-independent COMMAND Family1NearPairIndependent)
    add_executable(Family1CommonTailDistanceIndependent tests/Family1CommonTailDistanceIndependent.cpp)
    target_link_libraries(Family1CommonTailDistanceIndependent PRIVATE Family1OfflineCore)
    add_test(NAME family1-common-tail-distance-independent COMMAND Family1CommonTailDistanceIndependent)
    add_executable(Family1ScoredSeedsIndependent tests/Family1ScoredSeedsIndependent.cpp)
    target_link_libraries(Family1ScoredSeedsIndependent PRIVATE Family1OfflineCore)
    add_test(NAME family1-scored-seeds-independent COMMAND Family1ScoredSeedsIndependent)
    set_tests_properties(family1-scored-seeds-independent PROPERTIES TIMEOUT 180)
    add_executable(HardPairJointStartup tests/HardPairJointStartup.cpp)
    target_include_directories(HardPairJointStartup PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME hard-pair-joint-startup COMMAND HardPairJointStartup)
    add_executable(Family1JointPriorityIndependent tests/Family1JointPriorityIndependent.cpp)
    target_link_libraries(Family1JointPriorityIndependent PRIVATE Family1OfflineCore)
    add_test(NAME family1-joint-priority-independent COMMAND Family1JointPriorityIndependent)
    add_executable(HardPairJointBenchmark tests/HardPairJointBenchmark.cpp)
    target_include_directories(HardPairJointBenchmark PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_executable(HardPairJointAdaptiveIndependent tests/HardPairJointAdaptiveIndependent.cpp)
    target_include_directories(HardPairJointAdaptiveIndependent PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME hard-pair-joint-adaptive-independent COMMAND HardPairJointAdaptiveIndependent)
    add_executable(Family1AdaptiveWindowBenchmark tests/Family1AdaptiveWindowBenchmark.cpp)
    target_link_libraries(Family1AdaptiveWindowBenchmark PRIVATE Family1OfflineCore)
    set(FAMILY1_ADAPTIVE_COMPILE_SOURCES tests/Family1AdaptiveWindowBenchmark.cpp HardPairJointAdaptive.h
        Family1ScoredSeeds.h Family1TailScoredSeeds.h Family1JointPair.h Family1JointSeeds.h
        HardPairJointFinder.h HardPairPrefixSeeds.h Family1ExactPacked.h Family1ExactPacked.cpp
        Family1LargeGraph.h Family1LargeGraph.cpp Family1PairAgreement.h Family1CliArtifacts.h HardPairViability.h)
    set(FAMILY1_ADAPTIVE_COMPILE_FINGERPRINT "")
    foreach(FAMILY1_ADAPTIVE_SOURCE IN LISTS FAMILY1_ADAPTIVE_COMPILE_SOURCES)
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_ADAPTIVE_SOURCE}" FAMILY1_ADAPTIVE_FILE_SHA256)
        string(APPEND FAMILY1_ADAPTIVE_COMPILE_FINGERPRINT "${FAMILY1_ADAPTIVE_FILE_SHA256}\n")
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/${FAMILY1_ADAPTIVE_SOURCE}")
    endforeach()
    string(SHA256 FAMILY1_ADAPTIVE_SOURCE_SHA256 "${FAMILY1_ADAPTIVE_COMPILE_FINGERPRINT}")
    target_compile_definitions(Family1AdaptiveWindowBenchmark PRIVATE FAMILY1_ADAPTIVE_SOURCE_SHA256="${FAMILY1_ADAPTIVE_SOURCE_SHA256}")
    if(MSVC)
        set_property(TARGET Family1AdaptiveWindowBenchmark HardPairJointAdaptiveIndependent
            Family1NearPairIndependent Family1CommonTailDistanceIndependent
            Family1ScoredSeedsIndependent Family1JointPriorityIndependent
            HardPairJointStartup HardPairJointBenchmark PROPERTY
            MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
        set_target_properties(Family1AdaptiveWindowBenchmark HardPairJointAdaptiveIndependent
            Family1NearPairIndependent Family1CommonTailDistanceIndependent
            Family1ScoredSeedsIndependent Family1JointPriorityIndependent
            HardPairJointStartup HardPairJointBenchmark PROPERTIES
            VS_GLOBAL_VcpkgEnabled "false" VS_GLOBAL_VcpkgEnableManifest "false")
    endif()
    find_program(FAMILY1_JOINT_PYTHON NAMES python3 python)
    if(FAMILY1_JOINT_PYTHON)
        add_test(NAME family1-certified-cli COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_certified_test.py"
            --exe $<TARGET_FILE:Family1Certified>)
        set_tests_properties(family1-certified-cli PROPERTIES TIMEOUT 180)
        add_test(NAME family1-near-cli COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_near_cli_test.py"
            --exe $<TARGET_FILE:Family1NearPair>)
        set_tests_properties(family1-near-cli PROPERTIES TIMEOUT 180)
        add_test(NAME family1-joint-cli COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_joint_cli_test.py"
            --exe $<TARGET_FILE:Family1Joint>)
        set_tests_properties(family1-joint-cli PROPERTIES TIMEOUT 180)
        add_test(NAME hard-pair-joint-benchmark COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/hard_pair_joint_benchmark.py"
            --exe $<TARGET_FILE:HardPairJointBenchmark> --self-test)
        set_tests_properties(hard-pair-joint-benchmark PROPERTIES TIMEOUT 180)
        add_test(NAME hard-pair-witness-figure COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/hard_pair_witness_figure_test.py")
    endif()
    find_program(FAMILY1_OFFLINE_UV_EXECUTABLE NAMES uv)
    if(FAMILY1_OFFLINE_UV_EXECUTABLE)
        add_test(NAME family1-offline-cli COMMAND "${FAMILY1_OFFLINE_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_offline_cli_test.py"
            --exe $<TARGET_FILE:Family1Offline>)
        set_tests_properties(family1-offline-cli PROPERTIES
            WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" TIMEOUT 180)
    elseif(FAMILY1_JOINT_PYTHON)
        add_test(NAME family1-offline-cli COMMAND "${FAMILY1_JOINT_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_offline_cli_test.py"
            --exe $<TARGET_FILE:Family1Offline>)
        set_tests_properties(family1-offline-cli PROPERTIES
            WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" TIMEOUT 180)
    endif()
endif()
if(FAMILY1_OFFLINE_ONLY)
    return()
endif()

add_executable(ProductAutomata main.cpp RegPDFA.cpp)
add_executable(MatM mm.cpp RegPDFA.cpp)

add_library(ProductAutomataDeps INTERFACE)

find_package(Boost CONFIG REQUIRED COMPONENTS dynamic_bitset)
if(TARGET Boost::dynamic_bitset)
    target_link_libraries(ProductAutomataDeps INTERFACE Boost::dynamic_bitset)
else()
    target_include_directories(ProductAutomataDeps INTERFACE ${Boost_INCLUDE_DIRS})
endif()

if(WIN32)
    find_package(PThreads4W CONFIG QUIET)
endif()

find_package(flint CONFIG QUIET)
if(TARGET flint::flint)
    message(STATUS "Using FLINT package config target flint::flint")
    target_link_libraries(ProductAutomataDeps INTERFACE flint::flint)
else()
    message(STATUS "Using legacy FindFLINT/FindGMP modules")
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}")
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

# The exact graph search is independent of the generating-function executables.
add_library(Family1Core Family1Search.cpp GraphBasedPDFAEnumerator.cpp TwoRegularDigraph.cpp)
target_include_directories(Family1Core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(Family1Search family1_main.cpp)
target_link_libraries(Family1Search PRIVATE Family1Core)

# Symbolic word-pair search avoids explicit products of all 2^m masks.
find_package(Z3 CONFIG REQUIRED)
add_library(Family1Symbolic Family1SatSolver.cpp Family1LargeGraph.cpp Family1LayerSearch.cpp
    Family1LargeEnumerator.cpp Family1ExactPacked.cpp Family1Symbolic.cpp Family1Synthesis.cpp)
target_include_directories(Family1Symbolic PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(Family1Symbolic PRIVATE z3::libz3 Family1Core)
add_executable(Family1Explore family1_explore.cpp)
target_link_libraries(Family1Explore PRIVATE Family1Symbolic)
add_executable(Family1Threshold family1_threshold.cpp)
target_link_libraries(Family1Threshold PRIVATE Family1Symbolic)
add_executable(Family1Construct family1_construct.cpp)
target_link_libraries(Family1Construct PRIVATE Family1Symbolic)
add_executable(Family1Sample family1_sample.cpp)
target_link_libraries(Family1Sample PRIVATE Family1Symbolic)
# Edit generation is independent of both the scorer and its SAT dependencies.
add_executable(Family1Edit family1_edit.cpp Family1EditSearch.cpp Family1LargeGraph.cpp)
target_include_directories(Family1Edit PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(Family1Exhaustive family1_exhaustive.cpp)
target_link_libraries(Family1Exhaustive PRIVATE Family1Symbolic)
add_executable(Family1ProjectionVerify tests/Family1ProjectionVerify.cpp)
add_executable(Family1IndependentM5 tests/Family1IndependentM5.cpp)
add_executable(Family1LayerVerify tests/Family1LayerVerify.cpp)
add_executable(Family1M8LayerVerify tests/Family1M8LayerVerify.cpp)
add_executable(Family1ExhaustiveVerify tests/Family1ExhaustiveVerify.cpp)
add_executable(Family1GlobalCheck family1_global.cpp)
target_link_libraries(Family1GlobalCheck PRIVATE Family1Symbolic)

include(CTest)
if(BUILD_TESTING)
    # Generic finder audit uses only the standard library and its own explicit
    # heterogeneous DFA family; it does not link a Family 1 implementation.
    add_executable(HardPairFinderIndependent tests/HardPairFinderIndependent.cpp)
    target_include_directories(HardPairFinderIndependent PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME hard-pair-finder-independent COMMAND HardPairFinderIndependent)
    add_executable(HardPairPrefixSeedsIndependent tests/HardPairPrefixSeedsIndependent.cpp)
    target_include_directories(HardPairPrefixSeedsIndependent PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME hard-pair-prefix-seeds-independent COMMAND HardPairPrefixSeedsIndependent)
    add_executable(HardPairViabilityIndependent tests/HardPairViabilityIndependent.cpp)
    target_include_directories(HardPairViabilityIndependent PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME hard-pair-viability-independent COMMAND HardPairViabilityIndependent)
    add_executable(Family1PairAgreementVerify tests/Family1PairAgreementVerify.cpp Family1LargeGraph.cpp)
    target_include_directories(Family1PairAgreementVerify PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME family1-pair-agreement COMMAND Family1PairAgreementVerify)
    add_executable(Family1FullGuidanceVerify tests/Family1FullGuidanceVerify.cpp Family1LargeGraph.cpp)
    target_include_directories(Family1FullGuidanceVerify PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    add_test(NAME family1-full-guidance COMMAND Family1FullGuidanceVerify)
    add_executable(Family1Regression tests/Family1Regression.cpp)
    target_link_libraries(Family1Regression PRIVATE Family1Core)
    add_test(NAME family1-core COMMAND Family1Regression)
    add_executable(LegacyRegression tests/LegacyRegression.cpp
        BackToFirstDFA.cpp VectorEnumerator.cpp InfTwoRegularDigraphBackToZero.cpp
        TwoRegularDigraph.cpp PDFA.cpp ProductPDFA.cpp ProductDFAExperiment.cpp RegPDFA.cpp)
    target_include_directories(LegacyRegression PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    target_link_libraries(LegacyRegression PRIVATE ProductAutomataDeps)
    add_test(NAME legacy-regression COMMAND LegacyRegression)
    add_executable(Family1LargeGraphRegression tests/Family1LargeGraphRegression.cpp)
    target_link_libraries(Family1LargeGraphRegression PRIVATE Family1Symbolic)
    add_test(NAME family1-large-graph COMMAND Family1LargeGraphRegression)
    add_executable(Family1SymbolicRegression tests/Family1SymbolicRegression.cpp)
    target_link_libraries(Family1SymbolicRegression PRIVATE Family1Symbolic Family1Core)
    add_test(NAME family1-symbolic COMMAND Family1SymbolicRegression)
    add_executable(Family1SatRegression tests/Family1SatRegression.cpp)
    target_link_libraries(Family1SatRegression PRIVATE Family1Symbolic)
    add_test(NAME family1-sat COMMAND Family1SatRegression)
    add_executable(Family1SynthesisRegression tests/Family1SynthesisRegression.cpp)
    target_link_libraries(Family1SynthesisRegression PRIVATE Family1Symbolic Family1Core)
    add_test(NAME family1-global-synthesis COMMAND Family1SynthesisRegression)
    add_executable(Family1ExactPackedRegression tests/Family1ExactPackedRegression.cpp)
    target_link_libraries(Family1ExactPackedRegression PRIVATE Family1Symbolic)
    add_test(NAME family1-exact-packed COMMAND Family1ExactPackedRegression)
    add_executable(Family1LargeEnumeratorRegression tests/Family1LargeEnumeratorRegression.cpp)
    target_link_libraries(Family1LargeEnumeratorRegression PRIVATE Family1Symbolic)
    add_test(NAME family1-large-enumerator COMMAND Family1LargeEnumeratorRegression)
    add_executable(Family1LayerSearchRegression tests/Family1LayerSearchRegression.cpp)
    target_link_libraries(Family1LayerSearchRegression PRIVATE Family1Symbolic)
    add_test(NAME family1-layer-search COMMAND Family1LayerSearchRegression)
    # This integration audit compares every score with a complete exported run.
    # Fresh checkouts can generate the reference using the documented search.
    set(FAMILY1_M5_REFERENCE "${CMAKE_CURRENT_SOURCE_DIR}/out/family1-m1-m6/graphs.jsonl")
    if(EXISTS "${FAMILY1_M5_REFERENCE}")
        add_test(NAME family1-independent-m5 COMMAND Family1IndependentM5
            --reference "${FAMILY1_M5_REFERENCE}"
            --out "${CMAKE_CURRENT_BINARY_DIR}/independent-m5-$<CONFIG>")
    endif()
    find_program(FAMILY1_UV_EXECUTABLE NAMES uv)
    if(FAMILY1_UV_EXECUTABLE)
        add_test(NAME family1-construct-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_construct_cli_test.py"
            --exe $<TARGET_FILE:Family1Construct>)
        add_test(NAME family1-sample-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_sample_cli_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-guided-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_guided_cli_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-finder-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_finder_cli_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-finder-improvement-checkpoint COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_finder_improvement_checkpoint_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-adaptive-candidate-search COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_adaptive_candidate_search_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-viability-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_viability_cli_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-edit-candidates-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_edit_candidate_cli_test.py"
            --exe $<TARGET_FILE:Family1Edit>)
        add_test(NAME family1-graph-candidate-search COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_graph_candidate_search_test.py"
            --exe $<TARGET_FILE:Family1Sample>)
        add_test(NAME family1-edit-candidate-ranking COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_rank_edit_candidates_test.py")
        add_test(NAME family1-threshold-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_threshold_cli_test.py"
            --exe $<TARGET_FILE:Family1Threshold>)
        add_test(NAME family1-burnside COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_burnside_count.py" --max-m 7)
        add_test(NAME family1-layer-verify COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_layer_verify_test.py"
            --exe $<TARGET_FILE:Family1LayerVerify>)
        add_test(NAME family1-layer-parallel COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_layer_parallel_test.py"
            --exe $<TARGET_FILE:Family1LayerVerify>)
        add_test(NAME family1-m8-layer-verify COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_m8_layer_verify_test.py"
            --exe $<TARGET_FILE:Family1M8LayerVerify>)
        add_test(NAME family1-exhaustive-cli COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_exhaustive_cli_test.py"
            --exe $<TARGET_FILE:Family1Exhaustive>)
        add_test(NAME family1-exhaustive-verify COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_exhaustive_verify_test.py"
            --exe $<TARGET_FILE:Family1ExhaustiveVerify>)
        add_test(NAME family1-journal-merge COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_merge_journals_test.py")
        add_test(NAME family1-upper-witness-apply COMMAND "${FAMILY1_UV_EXECUTABLE}" run --no-project python
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/family1_apply_upper_witnesses_test.py")
        set_tests_properties(family1-construct-cli family1-sample-cli family1-guided-cli family1-finder-cli family1-finder-improvement-checkpoint family1-adaptive-candidate-search family1-viability-cli family1-edit-candidates-cli family1-graph-candidate-search family1-edit-candidate-ranking family1-threshold-cli family1-burnside family1-layer-verify family1-layer-parallel family1-m8-layer-verify family1-exhaustive-cli
            family1-exhaustive-verify family1-journal-merge family1-upper-witness-apply
            PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
    endif()
endif()
