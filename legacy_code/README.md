# UAM Noise Fairness Dashboard — Setup Guide

Interactive workshop tool for exploring fairness principles in Urban Air Mobility noise allocation over Austin, TX.

---

## Prerequisites

- **Python 3.11 or later** — [python.org/downloads](https://www.python.org/downloads/)
- A modern web browser (Chrome, Firefox, Edge)
- No Node.js or build tools required

Verify Python is installed:
```
python --version
```

---

## 1. Install Python dependencies

Open a terminal in the `legacy_code` folder (or any parent folder) and run:

```
pip install flask flask-cors z3-solver
```

Tested versions:
| Package | Version |
|---------|---------|
| flask | 3.1.3 |
| flask-cors | 6.0.2 |
| z3-solver | 4.16.0.0 |

If you have multiple Python installs, use `pip3` instead of `pip`.

---

## 2. Start the solver server

From the `legacy_code` folder, run:

```
python solver_server.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5050
 * Debug mode: on
```

**Leave this terminal open.** The solver must be running whenever you use the dashboard.

---

## 3. Open the dashboard

Open `dashboard_v2.html` directly in your browser. You can do this by:

- Double-clicking the file in File Explorer, or
- Dragging it into an open browser window, or
- In your browser: `File → Open File → dashboard_v2.html`

The URL bar will show something like `file:///...dashboard_v2.html`.

---

## 4. Using the tool

1. **Set Aircraft (N)** — number of aircraft to schedule (1–8)
2. **Set Route start → end** — pick a start and end neighborhood for each aircraft
3. **Choose Fairness Principles** — select one or more ethical frameworks (Equal, Sufficientarian are solver-connected; others are display-only)
4. **Configure Metrics** — toggle metrics on and set the D (noise cap) and U (disparity) constraints
5. **Click "Run Solver"** — the solver automatically finds the *minimum* number of timesteps needed
   - On success: the map updates and the right panel shows `✓ Feasible — minimum T = N`
   - On failure: an explanation is shown (e.g. start conflict, structural infeasibility)

---

## Troubleshooting

**"Error — is server running on port 5050?"**
The Python server is not running. Go back to Step 2 and start `solver_server.py`.

**"pip is not recognized"**
Python was not added to your PATH during installation. Re-run the Python installer and check **"Add Python to PATH"**, or use the full path: `C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe -m pip install ...`

**"ModuleNotFoundError: No module named 'flask'"**
The packages installed into a different Python environment. Try:
```
python -m pip install flask flask-cors z3-solver
```

**Port 5050 already in use**
Another process is using the port. Either stop that process or change the port number at the bottom of `solver_server.py` (`app.run(port=5050, ...)`) and update the fetch URL in `dashboard_v2.html` (`http://localhost:5050/solve`) to match.

**Solver returns "unsat" immediately**
- Relax **D** (increase the noise cap slider) or **U** (increase the disparity slider)
- Make sure aircraft start positions are not all at the same neighborhood when D=1
- Check that the chosen start and end neighborhoods are connected in the Austin adjacency graph
