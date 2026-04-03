# SpinLogger

iOS dylib that injects into Coin Master, replicating Nuovo Speeder features plus real-time spin logging to CSV.

## Features

- **Real-time CSV Logging** — Every spin result (reel_1, reel_2, reel_3, outcome, coins won, etc.) is appended to `spin_history.csv` immediately
- **Counter Overlays** — Draggable on-screen counters per symbol type (🔨 attack, 🐷 steal, ⭐ accumulation, 🛡 shield, 🎰 spins, 💰 goldSack)
- **Speed Multiplier** — Adjustable game speed (1x–50x)
- **Spin Target** — Alert after N spins, with auto-reset options
- **Auto-Reset** — Reset counters on 3-of-a-kind (per-symbol or global)
- **Tris Lock & Skip** — Lock onto specific cards during trading
- **Presets** — Save/load 2 configuration presets
- **CSV Share** — Share spin history via iOS share sheet (AirDrop, Files, etc.)

## Building

The dylib is built automatically via GitHub Actions on every push. Download `SpinLogger.dylib` from the Actions artifacts.

To build locally (macOS with Xcode):
```
make
```

## Installation

### Method 1: ESign (Recommended — on iPhone)

1. Download `SpinLogger.dylib` from GitHub Actions artifacts
2. Transfer to your iPhone (AirDrop, Files, etc.)
3. Open ESign → Import your Coin Master IPA
4. Tap the IPA → "Signature" → "Inject Dylib"
5. Select `SpinLogger.dylib`
6. Sign and install

### Method 2: Command Line (macOS)

```bash
./inject.sh CoinMaster.ipa SpinLogger.dylib
# Transfer the output IPA to phone, sign with ESign
```

## Usage

1. Launch Coin Master — a blue **SL** button appears on the right edge
2. Tap **SL** to open the settings menu
3. Counter overlays show per-symbol counts (drag to reposition)
4. Spin history is logged to `Documents/spin_history.csv` automatically
5. Use "Share CSV" in the menu to export the file

## CSV Format

| Column | Description |
|--------|-------------|
| spin_number | Server-side spin count |
| timestamp | When the spin was logged |
| reel_1 | Left reel symbol |
| reel_2 | Middle reel symbol |
| reel_3 | Right reel symbol |
| spin_result | Outcome (gold, attack, steal, shield, spins, noreward, accumulation) |
| coins_won | Coins won from this spin |
| bet_type | Bet multiplier (X1, X2, etc.) |
| auto_spin | Whether auto-spin was active |
| coins | Current coin balance |
| spins_remaining | Spins left |
| shields | Active shields |
| village | Current village number |
| active_pet | Active pet (FOX, TIGER, RHINO) |
| accum_bar_result | Per-reel accumulation bar bonus |
| sos_symbol | Accumulation event type (e.g., BluePotion) |
| all_time_spins | Total lifetime spins |

## Reel Symbols

`coin`, `shield`, `attack`, `steal`, `goldSack`, `spins`, `accumulation`
