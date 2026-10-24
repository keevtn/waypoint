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

export const markConnected = (): void => {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* ignore */
  }
};
