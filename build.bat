@echo off
REM Build script for Agent Engine on Windows
REM Usage: build.bat [command]

set PYTHON=python
set VENV=.venv

if "%1"=="" goto help
if "%1"=="install" goto install
if "%1"=="format" goto format
if "%1"=="lint" goto lint
if "%1"=="typecheck" goto typecheck
if "%1"=="test" goto test
if "%1"=="coverage" goto coverage
if "%1"=="clean" goto clean
goto help

:install
echo Creating virtual environment...
%PYTHON% -m venv %VENV%
echo Installing agent-engine with dev dependencies...
%VENV%\Scripts\python.exe -m pip install --upgrade pip
%VENV%\Scripts\python.exe -m pip install -e .[dev]
echo Installation complete!
goto end

:format
echo Formatting code with ruff...
%VENV%\Scripts\ruff.exe format src tests
goto end

:lint
echo Linting code with ruff...
%VENV%\Scripts\ruff.exe check src tests
goto end

:typecheck
echo Type checking with mypy...
%VENV%\Scripts\mypy.exe src
goto end

:test
echo Running tests...
set PYTHONPATH=src
%VENV%\Scripts\pytest.exe
goto end

:coverage
echo Running tests with coverage...
set PYTHONPATH=src
%VENV%\Scripts\pytest.exe --cov=agent_engine --cov-report=term-missing
goto end

:clean
echo Cleaning build artifacts...
if exist %VENV% rmdir /s /q %VENV%
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .mypy_cache rmdir /s /q .mypy_cache
if exist .ruff_cache rmdir /s /q .ruff_cache
if exist .coverage del /q .coverage
if exist htmlcov rmdir /s /q htmlcov
echo Clean complete!
goto end

:help
echo Usage: build.bat [command]
echo.
echo Available commands:
echo   install    - Create venv and install agent-engine with dev dependencies
echo   format     - Format code with ruff
echo   lint       - Lint code with ruff
echo   typecheck  - Type check with mypy
echo   test       - Run pytest
echo   coverage   - Run pytest with coverage
echo   clean      - Remove venv and cache directories
echo.

:end
