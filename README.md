# UAM Noise Solver

A Z3-powered dashboard for scheduling UAM (Urban Air Mobility) aircraft routes under noise constraints. The solver finds the **minimum time horizon** T such that all aircraft can travel from their start to end stations without violating per-station noise caps or adjacent-station disparity limits.

---

## Requirements

- Python 3.9 or newer
- A modern web browser (Chrome, Firefox, Edge)
- Internet connection on first load (Google Fonts + React loaded from CDN)

---

## Installation

### 1. Clone or download the project

```
git clone <repo-url>
cd EECS_199_Shoukry
```

Or just unzip the project folder — no build step needed.

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

> If you have multiple Python installs, use `pip3` or `python -m pip install ...` to ensure you're installing into the right environment.

---

## Running the dashboard

### Step 1 — Start the solver server

```
python solver_server.py
```

You should see:

```
 * Running on http://127.0.0.1:5050
```

Leave this terminal open while using the dashboard.

### Step 2 — Open the dashboard

Open `dashboard.html` directly in your browser:

- **Windows:** double-click `dashboard.html`, or drag it into a browser window
- **Mac/Linux:** `open dashboard.html` in terminal

No local web server is needed — the file runs entirely in-browser.

### Step 3 — Use the solver

1. Set **N** (aircraft count), **M** (station count), **D** (max noise per station), **U** (max adjacent disparity) using the sliders
2. Enter start and end station numbers for each aircraft
3. Toggle the **Adjacency Matrix** cells to define which station-to-station moves are allowed (row = from, col = to)
4. Click **Run Solver**

The dashboard will display the minimum feasible T, each aircraft's path, and a color-coded noise matrix.

---

## Saving and loading configs

Your current settings (sliders, positions, adjacency matrix) are **automatically saved** in the browser between sessions — no action needed.

To save a named config file or share settings with someone else:

- **Save Config** — downloads `uam-config.json` with the current settings
- **Load Config** — imports a previously saved `.json` file and restores all settings

---

## Project files

```
EECS_199_Shoukry/
├── solver_server.py        # Flask backend — Z3 solver, port 5050
├── dashboard.html          # Browser frontend — React (no build step)
├── aircraft_dynamics_solver.py   # Standalone Z3 script (reference/testing)
└── README.md
```

---

## Troubleshooting

**"Connection error — is the server running on port 5050?"**
Make sure `solver_server.py` is running in a separate terminal before opening the dashboard.

**"unsat" result**
Common causes and quick fixes:

| Reason shown | Fix |
|---|---|
| noise_cap | Increase D, decrease N, or increase M |
| start_conflict | Make sure no two aircraft share the same start station when D = 1 |
| unreachable | Check the adjacency matrix — every aircraft needs a connected path from start to end |
| structural | Noise/disparity constraints (D, U) conflict with the graph structure — try relaxing U or D |

**Port 5050 already in use**
Change the port in `solver_server.py` (last line) and update the `fetch` URL in `dashboard.html` to match.
