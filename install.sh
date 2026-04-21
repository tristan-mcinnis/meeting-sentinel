#!/usr/bin/env bash
# Meeting Sentinel installer
# Usage:  ./install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
SHIM="${BIN_DIR}/meet"

echo "Meeting Sentinel — installer"
echo "Repo: ${REPO_DIR}"
echo

# 1. Check prerequisites
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.9+ first."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg not found. Install it with:  brew install ffmpeg"
  echo "Meeting Sentinel needs ffmpeg to record audio."
fi

if ! system_profiler SPAudioDataType 2>/dev/null | grep -q -i "blackhole"; then
  echo "WARNING: BlackHole audio driver not detected."
  echo "Install it with:  brew install --cask blackhole-2ch"
  echo "(Then reboot — it's a kernel audio driver.)"
fi

# 2. Install Python deps
echo "Installing Python requirements..."
python3 -m pip install --user -r "${REPO_DIR}/requirements.txt"

# 3. Create the `meet` shim on PATH
mkdir -p "${BIN_DIR}"
cat > "${SHIM}" <<EOF
#!/usr/bin/env bash
exec python3 "${REPO_DIR}/meet.py" "\$@"
EOF
chmod +x "${SHIM}"
echo "Installed shim: ${SHIM}"

# 4. PATH hint
case ":${PATH}:" in
  *":${BIN_DIR}:"*)
    ;;
  *)
    echo
    echo "NOTE: ${BIN_DIR} is not on your PATH."
    echo "Add this to ~/.zshrc (or ~/.bashrc):"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

echo
echo "Installed. Next:"
echo "  meet setup       # pick paths + transcription provider"
echo "  meet devices     # verify BlackHole"
echo "  meet watch       # or: meet start / meet stop"
