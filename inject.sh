#!/bin/bash
# inject.sh — Inject SpinLogger.dylib into a Coin Master IPA
#
# Usage:  ./inject.sh <path-to-ipa> <path-to-SpinLogger.dylib>
# Output: <name>_SpinLogger.ipa in the current directory
#
# Requirements: insert_dylib (brew install insert_dylib) or optool
#
# To replace One.dylib entirely:
#   ./inject.sh "CMS One_3.5.2490.ipa" SpinLogger.dylib
# Then sign with ESign and install.

set -e

IPA="$1"
DYLIB="$2"

if [ -z "$IPA" ] || [ -z "$DYLIB" ]; then
    echo "Usage: $0 <CoinMaster.ipa> <SpinLogger.dylib>"
    exit 1
fi

WORK=$(mktemp -d)
echo "[*] Extracting IPA..."
unzip -q "$IPA" -d "$WORK"

APP=$(find "$WORK/Payload" -name "*.app" -maxdepth 1)
BINARY="$APP/$(defaults read "$APP/Info.plist" CFBundleExecutable)"
DYLIB_NAME="SpinLogger.dylib"

echo "[*] Copying dylib..."
cp "$DYLIB" "$APP/$DYLIB_NAME"

# Remove One.dylib if present (SpinLogger replaces it)
if [ -f "$APP/One.dylib" ]; then
    echo "[*] Removing One.dylib (replaced by SpinLogger)..."
    rm -f "$APP/One.dylib"
fi

echo "[*] Injecting load command..."
if command -v insert_dylib &> /dev/null; then
    insert_dylib --inplace --all-yes "@executable_path/$DYLIB_NAME" "$BINARY"
elif command -v optool &> /dev/null; then
    optool install -c load -p "@executable_path/$DYLIB_NAME" -t "$BINARY"
else
    echo "[!] Neither insert_dylib nor optool found."
    echo "    Install: brew install insert_dylib"
    exit 1
fi

# If One.dylib's load command is in the binary, remove it
if command -v optool &> /dev/null; then
    optool uninstall -p "@executable_path/One.dylib" -t "$BINARY" 2>/dev/null || true
fi

echo "[*] Repacking IPA..."
OUTPUT="${IPA%.ipa}_SpinLogger.ipa"
cd "$WORK"
zip -qr "$OLDPWD/$(basename "$OUTPUT")" Payload
cd "$OLDPWD"

echo "[*] Cleaning up..."
rm -rf "$WORK"

echo "[+] Done: $(basename "$OUTPUT")"
echo ""
echo "Next steps:"
echo "  1. Transfer to phone"
echo "  2. Sign with ESign"
echo "  3. Install and play"
