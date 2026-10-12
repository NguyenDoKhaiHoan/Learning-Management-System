import { api } from "../../../services/api/client";

/** Minimal client observations; the server is authoritative for ownership and time. */
export function observeAttempt(attemptId: string, current: () => boolean) {
  let lastSent = 0;
  let stopped = false;
  const send = (eventType: "TAB_HIDDEN" | "WINDOW_BLUR") => {
    if (stopped || !current() || Date.now() - lastSent < 1000) return;
    lastSent = Date.now();
    const body = {
      client_event_id: crypto.randomUUID(),
      event_type: eventType,
    };
    const record = () =>
      api.request(`/attempts/${attemptId}/events`, "POST", body);
    // A single retry reuses the identifier, so a lost response cannot duplicate a flag.
    void record()
      .catch(() => record())
      .catch(() => {});
  };
  const hidden = () => {
    if (document.visibilityState === "hidden") send("TAB_HIDDEN");
  };
  const blur = () => send("WINDOW_BLUR");
  document.addEventListener("visibilitychange", hidden);
  window.addEventListener("blur", blur);
  return () => {
    stopped = true;
    document.removeEventListener("visibilitychange", hidden);
    window.removeEventListener("blur", blur);
  };
}
