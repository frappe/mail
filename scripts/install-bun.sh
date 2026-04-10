#!/bin/bash

if ! command -v bun &> /dev/null; then
  echo "Bun not found. Installing..."
  npm install -g bun
else
  echo "Bun is already installed: $(bun --version)"
fi
