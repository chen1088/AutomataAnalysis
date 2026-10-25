WIP This is a C++ project that computes and visualizes the generating function of the product automata.

## Build

The project uses CMake and requires a C++23 compiler, Boost Dynamic Bitset, and
FLINT. The Windows build uses native MSVC and vcpkg.

### Windows: MSVC + vcpkg

Prerequisites:

- Visual Studio 2022 / Build Tools 2022 version 17.13 or newer, with the C++
  workload, Windows SDK, and C++ CMake tools for Windows
- CMake 3.28 or newer, either on PATH or bundled with Visual Studio
- Git

From PowerShell:

```powershell
Set-Location C:\path\to\AutomataAnalysis
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows-vcpkg.ps1
```

`-ExecutionPolicy RemoteSigned` applies only to this PowerShell process. The script
finds CMake on PATH or through Visual Studio's `vswhere`, uses an existing
`VCPKG_ROOT` or clones vcpkg into `.deps/vcpkg`, installs the manifest
dependencies, and builds the `msvc-vcpkg` Debug configuration. Visual Studio's
bundled vcpkg is replaced with the local checkout unless supplied explicitly
with `-VcpkgRoot`.

To build Release, append `-Configuration Release` to the command. To use a
separate vcpkg checkout, append `-VcpkgRoot C:\path\to\vcpkg`.

The manifest pins the vcpkg registry revision. A local [MPFR overlay](vcpkg-overlays/mpfr/README.md)
checks GMP limb width at compile time and supplies the matching Debug or Release
DLL path to the remaining configure probes. It preserves validation and requires
no changes to Windows code integrity or other protection settings.

Run the console example from the repository directory:

```powershell
.\out\build\msvc-vcpkg\Debug\ProductAutomata.exe
```

The build also produces `MatM.exe` in the same directory. Release executables
are under `out\build\msvc-vcpkg\Release`.

To build manually with an existing vcpkg installation:

```powershell
$env:VCPKG_ROOT = "C:\path\to\vcpkg"
cmake --preset msvc-vcpkg
cmake --build --preset msvc-vcpkg-debug
```

In the configured VS Code workspace, **Ctrl+Shift+B** builds Debug. Choose
**Build AutomataAnalysis (Release)** from **Tasks: Run Build Task** for Release.
Select **ProductAutomata (Windows Debug)** or **MatM (Windows Debug)** in
**Run and Debug**, then press **F5** to build and debug the console example.

Microsoft's C/C++ and CMake Tools extensions provide debugging and IntelliSense.
For CMake Tools, select `msvc-vcpkg` with **CMake: Select Configure Preset**, then
select the Debug or Release build preset. The local workspace settings supply
the bundled CMake path and `VCPKG_ROOT`; these machine-specific `.vscode` files
are ignored by Git. In a fresh workspace, set those paths for your installation
or use the PowerShell build command above.

### Linux / WSL

Install FLINT and GMP using your system package manager, or build them locally in
one of the paths searched by `FindFLINT.cmake` and `FindGMP.cmake`. Then run:

```bash
cmake -S . -B out/build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build out/build/debug
```
