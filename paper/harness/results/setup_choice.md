# Setup screen (session 3): which setups make every principle active?

Criterion per principle in `activity.py`. "Attributable" means the means differ by more than the larger permutation floor **and** the ranges do not overlap. Every cell below is K permutations, unlimited budget, proven.


## N = 8

| setup | Equal | Sufficientarian | Prioritarian | Utilitarian | Proportional | active | attributable diffs |
|---|---|---|---|---|---|---|---|
| `D5` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe

| `D5_protA` | no | no | no | -- | -- | **0/5** | 1/6 |

  - equal: utilisation 0.62, no attributable difference from the wide-cap baseline
  - sufficientarian: utilisation 0.50, no attributable difference from the wide-cap baseline
  - prioritarian: control peak 2.36 dB -> 0.00 dB with the objective on; within the band
  - utilitarian: no probe
  - proportional: no probe

| `D6` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe

| `D6_protA` | no | no | no | -- | -- | **0/5** | 1/6 |

  - equal: utilisation 0.62, no attributable difference from the wide-cap baseline
  - sufficientarian: utilisation 0.50, no attributable difference from the wide-cap baseline
  - prioritarian: control peak 2.36 dB -> 0.00 dB with the objective on; within the band
  - utilitarian: no probe
  - proportional: no probe

| `protA` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe


## N = 16

| setup | Equal | Sufficientarian | Prioritarian | Utilitarian | Proportional | active | attributable diffs |
|---|---|---|---|---|---|---|---|
| `D5` | yes | yes | no | -- | -- | **2/5** | 1/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: the protected set carries nothing even with the objective off (peak 0.00 dB) -- satisfied for free
  - utilitarian: no probe
  - proportional: no probe

| `D5_protA` | yes | yes | yes | yes | yes | **5/5** | 2/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: control peak 3.45 dB -> 0.00 dB with the objective on
  - utilitarian: dB total: baseline 38.2 -> 20.2 (gain 17.9 vs floor 16.1)
  - proportional: priced dB: baseline 762.2 -> 257.8 (gain 504.5 vs floor 16.1)

| `D6` | yes | yes | no | -- | -- | **2/5** | 1/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: the protected set carries nothing even with the objective off (peak 0.00 dB) -- satisfied for free
  - utilitarian: no probe
  - proportional: no probe

| `D6_protA` | yes | yes | yes | yes | yes | **5/5** | 2/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: control peak 3.45 dB -> 0.00 dB with the objective on
  - utilitarian: dB total: baseline 38.2 -> 20.2 (gain 17.9 vs floor 16.1)
  - proportional: priced dB: baseline 762.2 -> 257.8 (gain 504.5 vs floor 16.1)

| `protA` | no | no | yes | -- | -- | **1/5** | 0/6 |

  - equal: utilisation 0.31, no attributable difference from the wide-cap baseline
  - sufficientarian: utilisation 0.25, no attributable difference from the wide-cap baseline
  - prioritarian: control peak 5.20 dB -> 0.00 dB with the objective on
  - utilitarian: no probe
  - proportional: no probe


## N = 24

| setup | Equal | Sufficientarian | Prioritarian | Utilitarian | Proportional | active | attributable diffs |
|---|---|---|---|---|---|---|---|
| `D5` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe

| `D5_protA` | yes | yes | yes | -- | -- | **3/5** | 1/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: control peak 4.33 dB -> 0.00 dB with the objective on
  - utilitarian: no probe
  - proportional: no probe

| `D6` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe

| `D6_protA` | yes | yes | yes | -- | -- | **3/5** | 2/6 |

  - equal: cap binding exactly (utilisation 1.00)
  - sufficientarian: cap binding exactly (utilisation 1.00)
  - prioritarian: control peak 4.77 dB -> 0.00 dB with the objective on
  - utilitarian: no probe
  - proportional: no probe

| `protA` | -- | -- | -- | -- | -- | **0/5** | 0/6 |

  - equal: no cell
  - sufficientarian: no cell
  - prioritarian: no cell
  - utilitarian: no probe
  - proportional: no probe

