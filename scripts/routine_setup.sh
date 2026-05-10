#!/usr/bin/env bash
# Routine setup script — runs once per environment, result is cached.
# Paste this into the "Setup script" field when creating the Routine.
set -e

pip install --quiet -r requirements.txt

# Install Chromium for Playwright (needed for Facebook scraping)
playwright install chromium
playwright install-deps chromium
