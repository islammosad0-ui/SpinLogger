# SLDebtMonitor Design

**Date:** 2026-04-05
**Status:** Approved
**Component:** Real-time debt autocorrection + quiet zone betting assistant

## Overview

SLDebtMonitor is a new component for the SpinLogger iOS dylib that implements the debt autocorrection model and quiet zone detection to signal optimal max-bet windows during Coin Master GAE events. It tracks cumulative debt for both triple accumulation (ACC) and triple spins (SPN), detects quiet zones after non-target triples, and shows a glowing "BET NOW" tile when all conditions align.

## Architecture: Model + View Split (Approach C)

### Files

| File | Role |
|------|------|
| `src/SLDebtTracker.h/.m` | Pure logic model — debt calc, quiet zone detection, floor computation |
| `src/SLDebtMonitor.h/.m` | UI tiles + singleton + notification wiring |
| `src/SLSpinLogger.m` (modify) | Add `[[SLDebtMonitor shared] install]` call |

No changes to SLCounterOverlay or SLTrisController — SLDebtMonitor listens to the same `SLSpinReceivedNotification` independently.

## SLDebtTracker (Model)

### Per-Tracker State

- `debt` (NSInteger) — cumulative: `debt += (gap - target)` after each triple hit
- `saSpins` (NSInteger) — spins since last triple of this type
- `quietSpins` (NSInteger) — spins since last non-target triple (any combat/spins triple)
- `inQuietZone` (BOOL) — YES when quietSpins in range [quietMin, quietMax] after a non-target triple
- `phase` — enum: `SLDebtPhaseWaiting` (below floor), `SLDebtPhaseWatch` (above floor), `SLDebtPhaseBetNow` (quiet zone + above floor + in window)

### Configurable Parameters (per tracker, adjustable via long-press)

| Parameter | ACC Default | SPN Default | Description |
|-----------|-------------|-------------|-------------|
| `target` | 100 | 87 | Expected gap between triples |
| `floorBase` | 80 | 65 | Base floor before debt adjustment |
| `floorMin` | 20 | 20 | Absolute minimum floor |
| `quietMin` | 3 | 3 | Min spins of silence for quiet zone |
| `quietMax` | 7 | 7 | Max spins of silence for quiet zone |
| `betWindow` | 8 | 8 | Max spins to hold max bet |

### Key Methods

- `-(void)onSpin:(SLSpinResult *)spin` — increments saSpins, quietSpins, checks for triples, updates phase
- `-(SLDebtPhase)currentPhase` — returns computed phase
- `-(NSInteger)watchPoint` — returns `max(floorMin, floorBase - debt)`
- `-(void)reset` — zeros all state
- `-(void)saveState` / `-(void)restoreState` — NSUserDefaults persistence

### Phase Logic

```
watchPoint = max(floorMin, floorBase - debt)

if saSpins < watchPoint:
    phase = Waiting
elif saSpins >= watchPoint AND inQuietZone:
    phase = BetNow  (for up to betWindow spins)
elif saSpins >= watchPoint:
    phase = Watch
```

### Persistence Keys

- `Speeder_DebtACC` / `Speeder_DebtSPN` — tracker state dictionaries
- `Speeder_DebtEventID` — last seen event ID for auto-reset

## SLDebtMonitor (View)

### Two Draggable UIWindow Tiles

- Window level: `UIWindowLevelAlert + 260` (above existing overlays)
- ACC tile and SPN tile, each independent

### Tile Display (3 lines, expanded)

```
Top:    emoji + debt value     e.g. "🎰 -42"
Middle: saSpins / watchPoint   e.g. "67 / 80"
Bottom: phase text             "WAIT" | "WATCH" | "BET NOW"
```

### Tile Modes

- **Compact** (tap to toggle): emoji + phase only (~50x30pt)
- **Expanded** (default): all 3 lines (~90x60pt)

### Phase Colors

| Phase | Background | Border/Glow |
|-------|-----------|-------------|
| Waiting | Dark semi-transparent | None |
| Watch | Dark semi-transparent | Subtle amber border |
| BetNow (ACC) | Dark semi-transparent | Pulsing green glow |
| BetNow (SPN) | Dark semi-transparent | Pulsing blue glow |

### Glow Effect

`CABasicAnimation` on `layer.shadowColor` / `shadowRadius` / `shadowOpacity`, pulsing in-out loop. Stops when phase exits BetNow.

### Haptic Feedback

`UIImpactFeedbackGenerator` (heavy style) fires once when phase transitions to BetNow.

### Interactions

| Gesture | Action |
|---------|--------|
| Drag | Move tile, position saved to NSUserDefaults |
| Tap | Toggle compact/expanded |
| Long-press | UIAlertController with parameter fields + Reset button |

### Default Positions

Right edge of screen, ACC above SPN.

## Data Flow

```
SLSpinReceivedNotification
        |
        v
SLDebtMonitor.onSpinReceived:
   |-- Extract SLSpinResult from notification
   |-- Check event ID change --> auto-reset if new event
   |-- Forward to SLDebtTracker (ACC).onSpin(result)
   |-- Forward to SLDebtTracker (SPN).onSpin(result)
   |-- Update both tile UIs
   |-- If either phase == BetNow --> trigger glow + haptic
```

## Event Reset Behavior

- **Auto-reset:** Detects event ID change from spin data, zeros both trackers
- **Manual reset:** Available via long-press menu as fallback
- **Debt persists** across mission changes within the same event
- **Debt does NOT persist** across different weekly GAE events (cross-event corr = -0.05)

## Design Decisions

1. **Model + View split** — debt math will evolve with more data; separation lets us tweak formulas without touching UI
2. **Two separate tiles** — ACC and SPN have different parameters and fire independently
3. **Native UIKit** — WKWebView was recently reverted in tris controller; UIKit is lighter for simple tiles
4. **Configurable params** — upcoming 200+ gap data collection will likely refine values
5. **Independent listener** — no coupling to counter overlay or tris controller
