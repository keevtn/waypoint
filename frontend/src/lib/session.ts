// Per-tab memory of whether the user went through Connect, so a refresh restores the profile
// without skipping the Connect step on first visit. sessionStorage may be unavailable; fail closed.
const KEY = "waypoint.connected";

export const hasConnected = (): boolean => {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
};

const HORIZON_KEY = "waypoint.horizon";

/** Horizon survives a refresh in this tab, like the connected flag, so the restored baseline matches the selector. */
export const storedHorizon = (fallback: number): number => {
  try {
    const n = Number(sessionStorage.getItem(HORIZON_KEY));
    return [12, 60, 120].includes(n) ? n : fallback;
  } catch {
    return fallback;
  }
};

export const storeHorizon = (months: number): void => {
  try {
    sessionStorage.setItem(HORIZON_KEY, String(months));
  } catch {
    /* ignore */
  }
};

export const markConnected = (): void => {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* ignore */
  }
};
