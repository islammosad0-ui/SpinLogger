#!/bin/bash
# inject.sh — Inject SpinLogger.dylib into a Coin Master IPA
# Usage: ./inject.sh <path-to-ipa> <path-to-SpinLogger.dylib>
#
# Requirements: insert_dylib (brew install insert_dylib) or optool

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

echo "[*] Repacking IPA..."
OUTPUT="${IPA%.ipa}_SpinLogger.ipa"
cd "$WORK"
zip -qr "$OLDPWD/$(basename "$OUTPUT")" Payload
cd "$OLDPWD"

echo "[*] Cleaning up..."
rm -rf "$WORK"

echo "[✓] Done: $(basename "$OUTPUT")"
echo ""
echo "Next: Transfer to phone, sign with ESign, install."
