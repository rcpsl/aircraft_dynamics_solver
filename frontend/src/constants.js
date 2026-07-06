export const DEFAULT_N = 2;
export const DEFAULT_M = 5;
export const DEFAULT_D = 1;
export const DEFAULT_U = 2;
export const DEFAULT_ADJ = [
  [1,1,0,0,0],
  [0,1,1,0,0],
  [0,0,1,1,0],
  [0,0,0,1,1],
  [0,0,0,0,1],
];
export const DEFAULT_START = [1, 3];
export const DEFAULT_END   = [4, 5];
export const DEFAULT_ZONES = [1, 1, 1, 1, 1];
export const DEFAULT_DB_PER_CRAFT = 65;

export const STORAGE_KEY = "uam-config";

// Zones that benefit from UAM (transit access, economic activity, jobs) and
// should therefore accept a proportional share of noise burden.
export const BENEFIT_ZONE_IDS = [1, 2, 8, 9];

export const ZONES = [
  { id: 1, name: "Commercial Hub",      dba: 63, category: "Very Noisy Urban" },
  { id: 2, name: "Mixed-Use Corridor",  dba: 52, category: "Urban"            },
  { id: 3, name: "Affluent Enclave",    dba: 42, category: "Quiet Suburban"   },
  { id: 4, name: "Sacrifice Zone",      dba: 55, category: "Urban"            },
  { id: 5, name: "Institutional",       dba: 48, category: "Normal Suburban"  },
  { id: 6, name: "Aging-in-Place",      dba: 40, category: "Quiet Suburban"   },
  { id: 7, name: "Gentrifying",         dba: 58, category: "Noisy Urban"      },
  { id: 8, name: "Growing / Future",    dba: 50, category: "Normal Suburban"  },
  { id: 9, name: "Transit Double-Bind", dba: 50, category: "Normal Suburban"  },
];

export const ZONE_COLORS = {
  "Very Noisy Urban": "#b91c1c",
  "Noisy Urban":      "#c2410c",
  "Urban":            "#b45309",
  "Normal Suburban":  "#1d4ed8",
  "Quiet Suburban":   "#15803d",
};
