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
export const RESULTS_STORAGE_KEY = "uam-last-result";

// Zones that benefit from UAM (transit access, economic activity, jobs) and
// should therefore accept a proportional share of noise burden.
export const BENEFIT_ZONE_IDS = [3, 4, 5];   // Urban, Downtown, Airport

// Zones that already carry cumulative disadvantage and should receive
// prioritarian protection from additional UAM noise.
export const PROTECTED_ZONE_IDS = [1, 2];     // Suburban, Rural

export const ZONES = [
  { id: 1, name: "Suburban", dba: 45, category: "Suburban" },
  { id: 2, name: "Rural",    dba: 30, category: "Rural"    },
  { id: 3, name: "Urban",    dba: 65, category: "Urban"    },
  { id: 4, name: "Downtown", dba: 68, category: "Downtown" },
  { id: 5, name: "Airport",  dba: 70, category: "Airport"  },
];

// Sentinel zone id meaning "ambient level was hand-edited, no longer matches a
// preset zone's default dBA" — the Zones dropdown switches to this automatically.
export const CUSTOM_ZONE_ID = 0;

export const ZONE_COLORS = {
  "Downtown": "#b45309",
  "Rural":    "#15803d",
  "Suburban": "#1d4ed8",
  "Airport":  "#b91c1c",
  "Urban":    "#c2410c",
  "Custom":   "#57534e",
};
