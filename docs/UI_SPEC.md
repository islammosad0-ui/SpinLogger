# SpinLogger UI Specification (Cloning One.dylib / SPEEDER ELITE)

## Overview

The entire UI is a single floating system that expands/collapses from an icon button.

---

## 1. Floating Icon (Collapsed State)

- Small circular button (like current "SL" button)
- **On tap**: Icon disappears, main panel EXPANDS from its position
- **On drag**: Moves the icon position

---

## 2. Main Panel (Expanded State)

Appears when icon is tapped. Dark glassmorphism panel.

### Layout:
```
┌──────────────────────────────────────────┐
│  ✈  SPEEDER ELITE        [1.00x]   ⚙   │
│                                          │
│  [▶]  [−]  ═══════○════════  [+]  [✕]   │
│                                          │
│  [↺]  [SKIP]  [∞]  [📶]  [+]  [+]      │
└──────────────────────────────────────────┘
```

### Buttons:
- **✈ SPEEDER ELITE** — Title (non-interactive)
- **1.00x** — Speed badge (shows current multiplier)
- **⚙ (Gear)** — Opens Settings Panel (replaces main panel content)
- **▶ Play** — Toggle speed on/off (1x ↔ saved speed)
- **− / +** — Decrease/increase speed by 1
- **Slider** — Drag to set speed 1-50x
- **✕ Collapse** — Collapses panel back to floating icon (NOT a close/X — it's the minimize toggle in the controls row, circled in reference screenshot)
- **↺ Reset** — Reset all counters
- **SKIP** — Toggle tris skip mode
- **∞ (Infinity)** — Open tris monitor popup
- **📶 (Network)** — Open network monitor
- **+ buttons** — Future features / counter toggle

---

## 3. Settings Panel (⚙ Gear tap)

Replaces main panel content. Same dark box, two tabs at top.

### Layout:
```
┌──────────────────────────────────────────┐
│  [TRIS MONITOR]  [SPIN COUNTER]     [X]  │
│                                          │
│  === TRIS MONITOR TAB ===                │
│  ACTIVE MONITOR              [○ toggle]  │
│                                          │
│  LOCK TARGET                             │
│  [🔨] [🐷] [💊] [🛡] [🧪]              │
│                                          │
│  === SPIN COUNTER TAB ===                │
│  Same 5 symbol icons as toggles          │
│  [🔨] [🐷] [💊] [🛡] [🧪]              │
│  Tap to show/hide that counter           │
│  Active = colored, Hidden = grayed out   │
└──────────────────────────────────────────┘
```

### Tris Monitor Tab:
- **ACTIVE MONITOR toggle** — When ON, the tris monitor panel pops up
- **LOCK TARGET** — 5 symbol icons. Tap one to select as lock target
  - When locked symbol hits triple → CUT INTERNET (block game requests)
  - Prevents auto-spin from continuing when you're away
  - Only one can be locked at a time
  - Selected = highlighted, others = dim

### Spin Counter Tab:
- 5 symbol icons as visibility toggles
- **Tap** = toggle that counter's visibility on screen
- **Active** = colored icon, counter visible on screen
- **Hidden** = grayed out icon, counter hidden
- Each counter is independent

---

## 4. Tris Monitor Panel (Popup)

Separate floating panel that appears when ACTIVE MONITOR is ON.

### Layout (matching screenshot 3):
```
┌──────────────────────────────────────────┐
│  [🔨]   [🐷]   [💊]   [🛡]   [🧪]  [X] │
│  ─cyan─ ─pink─ ─cyan─ ─purp─ ─green─    │
│   28      3     139    398      2        │
│   11      5      75     50     18        │
│   29     10      40    121   4484        │
│   17      6      44    163     16        │
│    7     18      22     62     19        │
│    9     36      41     72     10        │
│                                          │
│  RESET                      SPIN: 4516   │
└──────────────────────────────────────────┘
```

- Each column = distances between triples for that symbol
- Newest at top
- Color-coded numbers (cyan, pink, cyan, purple, green)
- RESET clears all history
- SPIN shows total spins in session

---

## 5. Counter Tiles (On-screen)

Individual draggable tiles, one per visible symbol.

### Layout:
```
[🔨 28] [🐷 3] [💊 139] [🛡 398] [🧪 2]
```

- Dark rounded squares (56x74px)
- Icon on top, colored number below
- Colored bar at bottom edge
- Each tile is independently draggable
- Shows distance since last triple for that symbol
- Hidden/shown based on Spin Counter tab toggles

---

## 6. Network Lock (Tris Lock Feature)

When LOCK TARGET is set (e.g., pig):
1. User spins normally
2. On 3-pig triple → SpinLogger blocks ALL outgoing game requests
3. Auto-spin stops because server can't respond
4. User gets alert: "Lock triggered — 3x [pig] detected"
5. User manually resumes from the panel

This prevents overshooting when using auto-spin unattended.
