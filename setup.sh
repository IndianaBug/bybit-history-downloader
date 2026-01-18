#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "▶ Project directory: $PROJECT_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "▶ Creating virtual environment in .venv"
  python3 -m venv "$VENV_DIR"
else
  echo "▶ Virtual environment already exists"
fi

echo "▶ Activating virtual environment"
source "$VENV_DIR/bin/activate"

echo "▶ Upgrading pip"
python -m pip install --upgrade pip

echo "▶ Installing dependencies"
pip install \
  playwright \
  httpx \
  tqdm
  pytest

echo "▶ Installing Playwright browser (Chromium)"
python -m playwright install --with-deps chromium

echo
echo "✅ Setup complete"
echo
echo "Next steps:"
echo "  cd $PROJECT_DIR"
echo "  source .venv/bin/activate"
echo "  python main.py --help"

