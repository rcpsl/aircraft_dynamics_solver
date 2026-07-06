# UAM Noise Solver

A Z3-powered dashboard for scheduling UAM (Urban Air Mobility) aircraft routes under noise constraints. The solver finds the **minimum time horizon** T such that all aircraft can travel from their start to end stations without violating per-station noise caps or adjacent-station disparity limits.

---

## Requirements

- Python 3.9 or newer
- Node.js 18 or newer (for the Vite frontend)
- A modern web browser (Chrome, Firefox, Edge)

---

## Installation

### 1. Clone the project

```
git clone <repo-url>
cd EECS_199_Shoukry
```

### 2. Install Python dependencies

```
pip install flask flask-cors z3-solver
```

Verified working versions:

| Package | Version |
|---------|---------|
| Flask | 3.1.3 |
| flask-cors | 6.0.2 |
| z3-solver | 4.16.0.0 |

### 3. Install frontend dependencies

```
cd frontend
npm install
```

---

## Running

You always need two terminals — one for the solver backend, one for the frontend.

### Terminal 1 — Start the solver server (always required)

```
python solver_server.py
```

You should see:

```
 * Running on http://127.0.0.1:5050
```

### Terminal 2 — Start the frontend

**Option A — Vite dev server (recommended)**

```
cd frontend
npm run dev
```

Then open `http://localhost:5173/` in your browser. The page hot-reloads on every file save.

**Option B — Plain HTML (no build step)**

Open `dashboard.html` directly in your browser (double-click on Windows, or `open dashboard.html` on Mac/Linux). This version uses React from CDN and requires an internet connection on first load.

---

## Using the solver

1. Set **N** (aircraft count), **M** (station count), **D** (max noise per station), **U** (max adjacent disparity) using the sliders
2. Enter start and end station numbers for each aircraft
3. Toggle **Adjacency Matrix** cells to define allowed moves (row = from, col = to)
4. Assign zone types to each station in the **Zones** tab
5. Optionally enable **Minimize transit time** or **Reduce noise at protected stations** in the Optimization section
6. Click **Run Solver**

The dashboard displays the minimum feasible T, each aircraft's path, transit times, a color-coded aircraft matrix, and a dB-increase noise matrix per zone baseline.

---

## Saving and loading configs

Settings are **automatically saved** in the browser between sessions via `localStorage`.

- **Save Config** — downloads `uam-config.json` with the current settings
- **Load Config** — imports a previously saved `.json` file and restores all settings

---

## Project files

```
EECS_199_Shoukry/
├── solver_server.py              # Flask backend — Z3 solver, port 5050
├── dashboard.html                # Standalone frontend (React from CDN, no build)
├── frontend/                     # Vite + React frontend
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── index.css
│       ├── constants.js          # ZONES, ZONE_COLORS, defaults
│       ├── utils.js              # combinedDb, color helpers, transit time
│       ├── hooks/
│       │   └── useSolver.js      # all state, localStorage sync, API call
│       └── components/
│           ├── Slider.jsx
│           ├── GraphPanel.jsx    # draggable SVG station graph
│           ├── LeftPanel/        # SolverTab, ZonesTab, NoiseModelTab
│           └── RightPanel/       # PathsTable, TransitTable, NoiseMatrix
├── aircraft_dynamics_solver.py   # Standalone Z3 script (reference/testing)
└── README.md
```

---

## Troubleshooting

**"Connection error — is the server running on port 5050?"**
Make sure `solver_server.py` is running in a separate terminal before using the dashboard.

**"unsat" result**

| Reason shown | Fix |
|---|---|
| noise_cap | Increase D, decrease N, or increase M |
| start_conflict | Make sure no two aircraft share the same start station when D = 1 |
| unreachable | Check the adjacency matrix — every aircraft needs a connected path from start to end |
| structural | Noise/disparity constraints (D, U) conflict with the graph structure — try relaxing U or D |

**Port 5050 already in use**
Change the port in `solver_server.py` (last line) and update the `fetch` URL in both `frontend/src/hooks/useSolver.js` and `dashboard.html` to match.
