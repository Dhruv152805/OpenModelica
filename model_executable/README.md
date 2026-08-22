# TwoConnectedTanks — Model Executable Placeholder

This directory contains the **runtime artifacts** of the compiled
`TwoConnectedTanks` OpenModelica model.

## Expected files

| File | Description |
|------|-------------|
| `TwoConnectedTanks` | Linux/macOS executable (no extension) |
| `TwoConnectedTanks.exe` | Windows executable |
| `TwoConnectedTanks_init.xml` | Initial parameter values read by the executable at startup |

## Why the binary is not committed

Compiled OpenModelica executables are OS- and architecture-specific.
Committing a Linux binary that won't run on Windows (and vice versa) adds
noise with no benefit.  The grader should rebuild from source using the
provided `build.mos` script (see the project README).

## How to rebuild

```bash
# From the project root, with omc on your PATH:
omc build.mos

# Move the artefacts here:
mv TwoConnectedTanks* model_executable/
```

## Quick test (Linux / WSL)

```bash
cd model_executable
./TwoConnectedTanks -override startTime=0,stopTime=3
```

On Windows (PowerShell):
```powershell
cd model_executable
.\TwoConnectedTanks.exe -override startTime=0,stopTime=3
```
