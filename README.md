WIP This is a C++ project that computes and visualizes the generating function of the product automata.

## Build

The project uses CMake and requires a C++23 compiler plus FLINT.

### Windows: MSVC + vcpkg

Prerequisites:

- Visual Studio 2022 or Visual Studio Build Tools 2022 with the C++ workload
- CMake
- Git

From PowerShell:

```powershell
git clone <repo-url>
cd AutomataAnalysis
.\scripts\build-windows-vcpkg.ps1
```

The script uses `VCPKG_ROOT` if it is already set. Otherwise it clones vcpkg into
`.deps/vcpkg`, bootstraps it, configures the `msvc-vcpkg` CMake preset, and builds
the Debug configuration.

To build manually with an existing vcpkg installation:

```powershell
$env:VCPKG_ROOT = "C:\path\to\vcpkg"
cmake --preset msvc-vcpkg
cmake --build --preset msvc-vcpkg-debug
```

### Linux / WSL

Install FLINT and GMP using your system package manager, or build them locally in
one of the paths searched by `FindFLINT.cmake` and `FindGMP.cmake`. Then run:

```bash
cmake -S . -B out/build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build out/build/debug
```
