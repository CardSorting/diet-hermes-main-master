/**
 * Plain-language copy for DietCode — written for non-technical reviewers.
 * Soda parody tone without trademarked slogans.
 */

export const DIETCODE_PITCH =
  "DietCode is like a diet cola for your codebase: lighter risk, same refreshing results. The AI suggests edits in a safe sandbox—you review, approve, and we run tests before anything sticks.";

/** Static fallback before API health resolves — prefer useDietCodeBroccoli().isDemo */
export const DIETCODE_DASHBOARD_DEMO_MODE = false;

export const DIETCODE_DEMO_BANNER =
  "Preview walkthrough — BroccoliDB not connected. For a live agent, run dietcode --tui (or open Dashboard → Chat).";

export const DIETCODE_LIVE_BANNER =
  "Live BroccoliDB data — graph, hive sessions, and healing proposals from your workspace.";

/** Primary CTA when dashboard demo mode is on (no fake progress timers). */
export const DIETCODE_LIVE_AGENT_CTA = {
  label: "Open live agent",
  hint: "Runs the real Hermes TUI in Dashboard → Chat (embedded terminal).",
  chatPath: "/chat",
} as const;

export const DIETCODE_TAGLINES = [
  "Just for the diff of it.",
  "Break builds, not hearts.",
  "The pause that refreshes your CI.",
  "Live fizzfully. Ship responsibly.",
  "Zero-calorie diffs · maximum fizz.",
  "Crack open a fresh patch.",
] as const;

/** Rotating toast / log one-liners */
export const SODA_TOASTS = [
  "Tab pulled — shaker ready.",
  "Bubbles rising in the sandbox.",
  "Pour line armed — awaiting approval.",
  "Condensation on the diff glass.",
] as const;

export type DietCodeTabId = "home" | "quality" | "activity";

export const DIETCODE_TABS: {
  id: DietCodeTabId;
  label: string;
  shortLabel: string;
  description: string;
  icon: "home" | "chart" | "list";
}[] = [
  {
    id: "home",
    label: "Run a session",
    shortLabel: "Home",
    description: "Set up a change, review it, and approve",
    icon: "home",
  },
  {
    id: "quality",
    label: "Quality checks",
    shortLabel: "Checks",
    description: "Automated test runs and success rates",
    icon: "chart",
  },
  {
    id: "activity",
    label: "Activity log",
    shortLabel: "Log",
    description: "What happened, step by step",
    icon: "list",
  },
];

export const HOW_IT_WORKS = [
  {
    step: 1,
    title: "Choose project & task",
    body: "Pick which repo to work in and what kind of help you want (tests, types, etc.).",
  },
  {
    step: 2,
    title: "Review the proposal",
    body: "See exactly which files would change—nothing happens until you say yes.",
  },
  {
    step: 3,
    title: "Approve & verify",
    body: "We apply the edit, run your tests, and keep a backup if you need to undo.",
  },
] as const;

export type SessionStatus =
  | "idle"
  | "preflight"
  | "proposed"
  | "applying"
  | "testing"
  | "success"
  | "violation"
  | "reverted";

export const SESSION_STATUS_COPY: Record<
  SessionStatus,
  { label: string; hint: string; tone: "neutral" | "wait" | "ok" | "warn" | "bad" }
> = {
  idle: {
    label: "Ready to pour",
    hint: "Configure your session below, then tap Start.",
    tone: "neutral",
  },
  preflight: {
    label: "Shaking the can…",
    hint: "Checking safety rules before we open anything.",
    tone: "wait",
  },
  proposed: {
    label: "Waiting for your OK",
    hint: "Review the proposed changes and approve or reject.",
    tone: "wait",
  },
  applying: {
    label: "Pouring changes…",
    hint: "Applying your approved edit in an isolated workspace.",
    tone: "wait",
  },
  testing: {
    label: "Running tests…",
    hint: "Making sure nothing broke before we call it done.",
    tone: "wait",
  },
  success: {
    label: "All fizzy!",
    hint: "Changes applied and tests passed.",
    tone: "ok",
  },
  violation: {
    label: "Over the pour line",
    hint: "A safety limit was exceeded—we rolled back automatically.",
    tone: "bad",
  },
  reverted: {
    label: "Spill cleaned up",
    hint: "Workspace restored from backup.",
    tone: "warn",
  },
};

export const WORKFLOW_STEPS = [
  { id: 1, label: "Intent", plain: "Request received" },
  { id: 2, label: "Safety", plain: "Rules checked" },
  { id: 3, label: "Proposal", plain: "Changes previewed" },
  { id: 4, label: "Approve", plain: "You said yes" },
  { id: 5, label: "Apply", plain: "Edits applied" },
  { id: 6, label: "Verify", plain: "Tests passed" },
] as const;

export const OPERATOR_FLAVORS: Record<
  string,
  { friendlyName: string; emoji: string; oneLiner: string }
> = {
  TestFixOperator: {
    friendlyName: "Test fix",
    emoji: "🧪",
    oneLiner: "Fix failing tests only",
  },
  RefactorOperator: {
    friendlyName: "Refactor",
    emoji: "✨",
    oneLiner: "Tidy code in allowed folders",
  },
  TypingOperator: {
    friendlyName: "Types",
    emoji: "📐",
    oneLiner: "Add or update TypeScript types",
  },
  DependencyUpgradeOperator: {
    friendlyName: "Dependencies",
    emoji: "📦",
    oneLiner: "Bump packages safely",
  },
};

export const SETUP_SECTIONS = {
  project: {
    title: "Which project?",
    hint: "The codebase the AI will work inside.",
  },
  flavor: {
    title: "What kind of help?",
    hint: "Each flavor limits where the AI can edit—safer by design.",
  },
  budget: {
    title: "Safety limits",
    hint: "Caps on files, time, and tool use—like a diet serving size.",
  },
} as const;
