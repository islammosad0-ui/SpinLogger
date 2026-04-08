# Game Binary Reverse Engineering — Path to Zoran-Level Precision

> Why the CSV-log analysis plateaus at ~6-20 mb/hit, and how to actually crack
> Coin Master's slot machine by looking inside the game binary.

---

## The ceiling we hit with CSV logs

After 20+ analysis chunks, 28,923 spins, and fixing a critical phantom-catch
bug, the best causally-validated signals we found are:

| Rule | Catches | mb/hit |
|------|---------|--------|
| STEAL t=150 g=0.30 | 5/271 | 6.2 |
| STEAL+SUPP last_10≤10 t=130 | 4/271 | 6.0 |
| Causal ensemble (6 rules) | ~35 | ~22 |

**We can't go lower than ~6 mb/hit from log analysis alone.** The game uses
weighted probability tables per bet level, and log data only lets us measure
the tail bias, not reverse-engineer the tables themselves.

**Zoran's claimed 2.3 mb/hit is almost certainly from a different data source**
— either reading the game binary (decompilation) or scraping runtime memory.

---

## Three approaches, ranked by effort vs payoff

### 1. Runtime memory scraping (Frida) — BEST PATH
**Effort**: medium    **Payoff**: high    **Legality**: personal use OK

Frida is a dynamic instrumentation toolkit for iOS/Android. You attach it to
a running Coin Master process and hook functions that read/write the slot
machine state. Instead of analyzing what the game tells the server, you
**read the game's RNG seed, probability tables, and current position**
directly from memory.

**Workflow on jailbroken iOS (or non-JB with Sideloadly + Frida gadget):**

```bash
# 1. Install Frida on Mac/Linux (iOS control host)
pip install frida-tools

# 2. Get the Coin Master app running and find its PID
frida-ps -Uai | grep -i coin

# 3. Attach and explore
frida -U "Coin Master"

# 4. In the Frida REPL, list loaded modules
[device]-> Process.enumerateModules()

# 5. Find the slot machine binary (usually "CoinMaster" or "UnityFramework")
[device]-> Module.load("/path/to/binary").enumerateExports()
```

**What to hook for ACC triple prediction:**
- The function that generates reel positions per spin (RNG call)
- The function that checks for "3x matching symbols" (triple detection)
- The `accumulation_progress` field in the game state
- The `bet_level` multiplier table

**Target symbols to search for** (based on Unity + typical slot naming):
```
UnityEngine.Random.Range
SlotMachine.Spin
SlotMachine.GenerateReels
Reel.GetSymbolAt
AccumulationMeter.Update
```

**Tools**:
- **Frida-server** (on device) + **Frida CLI** (on host)
- **frida-trace** to log function calls with arguments in real-time
- **Ghidra** or **Hopper** to find function addresses statically
- **r2frida** (radare2+frida bridge) for deeper exploration

### 2. Static binary decompilation (Ghidra / IDA / Hopper) — HARDEST
**Effort**: very high    **Payoff**: very high (table extraction)    **Legality**: personal use OK

Download the Coin Master IPA, extract it, and decompile the binary. The
probability tables are typically stored as serialized data in the Unity
Resources or ScriptableObjects.

**Workflow**:
```bash
# 1. Get the decrypted IPA (AppSync or from device)
# 2. Unzip IPA, find Payload/CoinMaster.app/CoinMaster or UnityFramework
cd Payload/CoinMaster.app/
unzip -l CoinMaster

# 3. Check for Unity's Il2Cpp (C# compiled to C++)
ls Data/Managed/Metadata/
# global-metadata.dat is Il2Cpp's symbol/string database

# 4. Use Il2CppDumper to reconstruct C# signatures
# https://github.com/Perfare/Il2CppDumper
./Il2CppDumper CoinMaster global-metadata.dat

# 5. Open the generated dump.cs in an editor, search for:
#    - SlotMachine, Reel, Spin, Triple, Accumulation
#    - probability, weight, table, RNG, random
```

**What you're looking for**:
- A C# class like `SlotMachineConfig` with fields like `reelStrips`, `symbolWeights`, `pityThreshold`
- A serialized asset bundle (`.assets` file) containing ScriptableObjects
  with probability tables

**Expected files in Coin Master app bundle**:
```
Data/StreamingAssets/
  aa/ (Addressables — bundle-based resources)
  bundles/
Data/Managed/Metadata/global-metadata.dat   ← key file for Il2Cpp dump
Data/Resources/unity_default_resources      ← legacy resources
```

**Tools**:
- **Il2CppDumper** — reconstructs C# from Il2Cpp-compiled Unity binaries (free)
- **Ghidra** — free, NSA's decompiler, supports ARM64 iOS binaries
- **IDA Pro** — commercial ($$$$), industry standard
- **Hopper Disassembler** — commercial ($$), Mac-native
- **UnityPy** — Python library to extract Unity asset bundles

### 3. Network traffic deep-dive (what we already do)
**Effort**: low    **Payoff**: low    **Legality**: clear

This is what SpinLogger already does — intercept the HTTP(S) spin responses
and log them. We already extract everything the server sends back. Nothing
more to discover here.

**However**, there might be **under-utilized fields** in the existing server
responses we haven't examined:
- `event_bars` JSON blob (raw) — contains rich event state
- `slot2_r1/r2/r3` — secondary slot machine (unused?)
- `spin_result` string — might encode multi-outcome hints
- `reward_code` — numeric ID for the reward type
- Response headers — `X-*` custom headers sometimes leak server state

---

## What Zoran probably does

Looking at the claimed precision (2-3 mb/hit, 20% catch rate consistently),
my best guess is:

1. **Il2Cpp dumped the binary** to get the probability table shape
2. **Frida-hooked the RNG call** to read the current seed in real-time
3. **Replicated the RNG algorithm** (probably Unity's `UnityEngine.Random.Range`
   which is a deterministic XorShift variant)
4. **Knowing the seed**, simulates future spins and shows the user
   "your next triple will land on spin N"

This is **not** log analysis. It's direct game-state reading. That's the
ceiling we can't reach with our current data pipeline.

---

## Realistic next steps for SpinLogger

### Phase 1 — DONE (this commit)
- Causal simulator + real-data ensemble
- Account-named CSVs
- S/M/L prediction display

### Phase 2 — Data collection (next 2-3 months)
- Keep the new tracker active during normal play
- Collect ~100K additional spins across all accounts
- When Nick has 100+ gaps, retry per-account profiles

### Phase 3 — Binary exploration (ambitious)
- Get a jailbroken iOS device or Android rooted device
- Install Frida-server
- Dump the Il2Cpp metadata (`global-metadata.dat`)
- Search for slot machine-related symbols
- Hook `UnityEngine.Random.Range` and see if we can predict the next value

### Phase 4 — Table extraction (if binary dump reveals structure)
- Extract the probability tables from ScriptableObjects
- Build a "theoretical" simulator that matches the game exactly
- At that point, 2 mb/hit becomes achievable

---

## Legal notes

- **Personal use** of Frida/Ghidra on apps you own a copy of is legal in most
  jurisdictions (reverse engineering for interoperability/research).
- **Distributing** the extracted probability tables or modified binaries is
  NOT legal (copyright).
- **Exploiting** the discovered tables to win money/items that get traded or
  sold may violate the game's ToS and result in a ban.
- **For personal learning**, this is fine.

---

## Tools list

**Install these on your Mac/Linux host:**
```bash
pip install frida-tools     # Dynamic instrumentation
pip install Il2CppDumper    # Unity Il2Cpp dumping
brew install ghidra         # (or download from ghidra-sre.org)
brew install radare2        # Static disassembler
brew install plistutil      # Parse iOS plist files
```

**Device-side (jailbroken iOS):**
- Frida-server (from Cydia or manual install)
- cycript / substitute / sileo
- Clutch or AppSync (to decrypt IPAs)

**Android (rooted):**
- Frida-server
- Xposed framework
- APKTool

---

## Summary

**The analysis-path has a ceiling at ~6 mb/hit.** The binary-path can
theoretically reach Zoran's 2 mb/hit BUT requires:
1. Jailbroken device or rooted Android
2. Il2CppDumper + Ghidra/Hopper
3. Frida + scripting skills
4. Weeks of exploration through decompiled code

It's a 10-50x effort increase for a 2-3x precision gain. Whether that's
worth it depends on what you actually want from this tool:
- **Tool for competitive play**: binary path is the way
- **Research project**: stay with log analysis, ship causal ensemble, keep
  collecting data

Right now we're on the research path, and the causal ensemble we just
shipped is the best that path can give you.
