/**
 * Soda-style log lines and UI callbacks for DietCode control plane.
 * Plain language + parody tone (no trademarked slogans).
 */

export type SodaLogTone = "info" | "success" | "warn" | "error" | "telemetry";

export interface SodaLogLine {
  msg: string;
  type: SodaLogTone;
  /** Optional CSS class hook */
  className?: string;
}

/** Startup / session lifecycle — use with appendLog */
export const SODA_BOOT_LINES: SodaLogLine[] = [
  { msg: "🫧 Shaker pressurized — DietCode control plane online.", type: "success" },
  { msg: "Carbonation lines primed. Waiting for your pour…", type: "info" },
  { msg: "Tab safety: nothing applies until you approve.", type: "info" },
];

export const SODA_SESSION_START: SodaLogLine[] = [
  { msg: "Cracking the tab — enqueuing workspace checkout…", type: "info" },
  { msg: "Worker fizz: disposable workspace spun up.", type: "success" },
  { msg: "Safety fizz: profile bounds verified.", type: "success" },
  { msg: "Proposal carbonated — checkpoint on ice.", type: "success" },
  { msg: "Worker on standby (event-driven wakeup).", type: "warn" },
];

export const SODA_APPROVE_LINES: SodaLogLine[] = [
  { msg: "Approval fizz received — policy bounds match.", type: "success" },
  { msg: "Args hash verified — same proposal, no surprise pour.", type: "success" },
  { msg: "Dispatching resume to the job shaker…", type: "info" },
];

export const SODA_APPLY_SUCCESS: SodaLogLine[] = [
  { msg: "Pour complete — post-mutation snapshot canned.", type: "success" },
  { msg: "Test shaker running…", type: "info" },
  { msg: "Tests: all fizzy (exit 0).", type: "success" },
  { msg: "Final snapshot sealed — workspace rinsed.", type: "success" },
  { msg: "Session flat-out success — within budget.", type: "success" },
];

export const SODA_SPILL_LINES: SodaLogLine[] = [
  { msg: "HALT — over the pour line (file budget).", type: "error" },
  { msg: "Spill protocol: rolling back to pre-mutation fizz…", type: "warn" },
  { msg: "Rollback poured — workspace restored.", type: "success" },
  { msg: "Worker can crushed — session ended.", type: "error" },
];

export const SODA_FLAVOR_SWITCH = (name: string): SodaLogLine => ({
  msg: `Flavor switched to ${name} — serving size updated.`,
  type: "info",
});

export const SODA_REPO_SWITCH = (name: string): SodaLogLine => ({
  msg: `New pour target: ${name}`,
  type: "info",
});

export const SODA_CANCEL = (): SodaLogLine => ({
  msg: "Session cancelled — tab never opened.",
  type: "warn",
});

/** Rotating one-liners for telemetry / quality tab */
export const SODA_TELEMETRY_LINES = [
  "Benchmark shaker: 250 operators, 98.4% fizzy.",
  "Rollback rate: 1.6% — mostly foam, not fire.",
  "Golden pour suite complete.",
] as const;
