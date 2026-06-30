@echo off
REM EllipticZero: https://github.com/ECD5A/EllipticZero
REM Copyright (c) 2026 ECD5A
REM SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
REM License terms: see LICENSE in the project root.

setlocal
cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -File ".\scripts\setup_local_lab.ps1" %*
endlocal
