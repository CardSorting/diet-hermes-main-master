import { useState, useEffect, useRef, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Shield,
  Terminal,
  FileText,
  Database,
  Download,
  TrendingUp,
  Activity,
  Gauge,
  ExternalLink,
  Check,
  X,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DietCodeHeader,
  DietCodePageNav,
  DietCodeSessionBanner,
  DietCodeShell,
  DietCodeWorkflowStepper,
  OPERATOR_FLAVORS,
  SETUP_SECTIONS,
  DIETCODE_DASHBOARD_DEMO_MODE,
  DIETCODE_LIVE_AGENT_CTA,
  DIETCODE_PITCH,
  SODA_BOOT_LINES,
  SODA_FLAVOR_SWITCH,
  SODA_REPO_SWITCH,
  type DietCodeTabId,
  type SessionStatus,
} from "@/components/dietcode";
import { useDietCodeBroccoli } from "@/hooks/useDietCodeBroccoli";

const CARD_SODA = "dc-card-soda border border-current/20";

/** Maps friendly nav ids to legacy internal tab state keys. */

// Define Bounded Operator Capability Profiles
interface OperatorProfile {
  name: string;
  description: string;
  permittedFiles: string;
  restrictedCommands: string;
  primaryPurpose: string;
}

const OPERATOR_PROFILES: OperatorProfile[] = [
  {
    name: "TestFixOperator",
    description: "Restricted strictly to fixing test files and writing tests.",
    permittedFiles: "**/src/__tests__/**, **/*.test.ts",
    restrictedCommands: "Edits to production code (src/core/*) blocked",
    primaryPurpose: "Fixes unit test failures and expands test suites.",
  },
  {
    name: "RefactorOperator",
    description: "Allowed to make structural code improvements.",
    permittedFiles: "**/src/local/fabric/**",
    restrictedCommands: "Modifying package lockfiles or API clients blocked",
    primaryPurpose: "Cleans up technical debt within explicit domains.",
  },
  {
    name: "TypingOperator",
    description: "Restricted strictly to adding and updating TypeScript types.",
    permittedFiles: "**/*.d.ts, **/*.types.ts",
    restrictedCommands: "All runtime JS/TS logic edits blocked",
    primaryPurpose: "Hardens static type safety boundaries.",
  },
  {
    name: "DependencyUpgradeOperator",
    description: "Allowed to edit only package configurations.",
    permittedFiles: "package.json, package-lock.json",
    restrictedCommands: "All source file editing blocked",
    primaryPurpose: "Performs version bumps and package installations.",
  },
];

// Define Repositories
const DETECTED_REPOS = [
  {
    name: "diet-hermes",
    framework: "Vite + React",
    packageManager: "pnpm",
    testCommand: "pnpm test",
    buildCommand: "pnpm build",
  },
  {
    name: "broccolidb",
    framework: "TypeScript Engine",
    packageManager: "bun",
    testCommand: "bun test",
    buildCommand: "bun run build",
  },
  {
    name: "nous-ui",
    framework: "Next.js + Tailwind",
    packageManager: "npm",
    testCommand: "npm run test",
    buildCommand: "npm run build",
  },
];

// Mock Unified Diffs per profile
const MOCK_DIFFS: Record<string, { path: string; diff: string }> = {
  TestFixOperator: {
    path: "ui-tui/src/__tests__/spine.test.ts",
    diff: `--- a/ui-tui/src/__tests__/spine.test.ts
+++ b/ui-tui/src/__tests__/spine.test.ts
@@ -10,6 +10,12 @@
   it("should enforce Bounded Operator pipeline constraints", () => {
     const pipeline = new VerifiedExecutionPipeline("/tmp/workspace");
     expect(pipeline.getBudget().maxFiles).toBe(10);
+  });
+
+  it("should enforce strict hash binding for alpha", () => {
+    const pipeline = new VerifiedExecutionPipeline("/tmp/workspace");
+    const result = pipeline.verifyProposal("args-hash-ok", "policy-hash-ok");
+    expect(result.valid).toBe(true);
   });
 };`,
  },
  RefactorOperator: {
    path: "ui-tui/src/local/fabric/spine.ts",
    diff: `--- a/ui-tui/src/local/fabric/spine.ts
+++ b/ui-tui/src/local/fabric/spine.ts
@@ -42,6 +42,9 @@
   public applyChanges(proposal: Proposal): void {
     this.boundary.checkContainment(proposal.path);
     this.boundary.backupOriginalFile(proposal.path);
+    
+    // Optimized single-node filesystem mutation write
+    this.boundary.writeFile(proposal.path, proposal.content);
     this.eventLog.log("changes.applied", { path: proposal.path });
   }
 }`,
  },
  TypingOperator: {
    path: "ui-tui/src/local/fabric/spine.types.ts",
    diff: `--- /dev/null
+++ b/ui-tui/src/local/fabric/spine.types.ts
@@ -0,0 +1,8 @@
+export interface SessionBudget {
+  maxFiles: number;
+  maxRuntimeMinutes: number;
+  maxToolCalls: number;
+  maxPatchSize: number;
+  maxTestRuntimeMinutes: number;
+}
+`,
  },
  DependencyUpgradeOperator: {
    path: "package.json",
    diff: `--- a/package.json
+++ b/package.json
@@ -25,3 +25,3 @@
   "devDependencies": {
-    "vitest": "^0.28.0",
+    "vitest": "^1.6.0",
     "typescript": "^5.0.4"`,
  },
};

/** Static example for dashboard demo mode (no setTimeout fake progress). */
const DEMO_EXAMPLE_STATUS: SessionStatus = "proposed";

export default function DietCodePage() {
  const broccoli = useDietCodeBroccoli();
  const isDemo = broccoli.isLoading ? DIETCODE_DASHBOARD_DEMO_MODE : broccoli.isDemo;

  // Navigation header setup
  const [activeRepo, setActiveRepo] = useState(DETECTED_REPOS[0]);
  const [activeProfile, setActiveProfile] = useState(OPERATOR_PROFILES[0]);
  const [budgetLimit] = useState({
    maxFiles: 10,
    maxRuntimeMinutes: 15,
    maxToolCalls: 25,
    maxPatchSize: 5000,
    maxTestRuntimeMinutes: 5,
  });

  // Live workflow state (disabled in demo mode — use DEMO_EXAMPLE_STATUS for preview UI)
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");
  const displayStatus = isDemo ? DEMO_EXAMPLE_STATUS : broccoli.sessionStatus || sessionStatus;
  const pendingProposal = useMemo(() => {
    if (isDemo || !broccoli.snapshot?.proposals?.length) return null;
    const pendingId = broccoli.snapshot.pending_proposal_id;
    if (pendingId) {
      return broccoli.snapshot.proposals.find((p) => p.id === pendingId) ?? null;
    }
    return (
      broccoli.snapshot.proposals.find((p) => (p.status || "").toLowerCase() === "pending") ?? null
    );
  }, [broccoli.snapshot, isDemo]);
  const [activeTab, setActiveTab] = useState<DietCodeTabId>("home");
  const [logs, setLogs] = useState<string[]>([]);
  const demoBudgetUsage = {
    files: 1,
    runtime: 1,
    toolCalls: 3,
    patchSize: 280,
    testRuntime: 0,
  };
  const [wakeupsCount] = useState(0);
  const [budgetUsage, setBudgetUsage] = useState(
    isDemo
      ? demoBudgetUsage
      : {
          files: 0,
          runtime: 0,
          toolCalls: 0,
          patchSize: 0,
          testRuntime: 0,
        }
  );
  const displayBudgetUsage = isDemo ? demoBudgetUsage : budgetUsage;

  const [argsHash] = useState("sha256-a4c892b11ef937a01dcd4a22c5e4f71a9b23e80d");
  const [policyHash] = useState("sha256-8c42ff65aef33b0dd4a221f7c9e0134b3f114ea2");

  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Helper to append observable logs
  const appendLog = (msg: string, type: "info" | "success" | "warn" | "error" | "telemetry" = "info") => {
    const timestamp = new Date().toISOString().substring(11, 19);
    let prefix = "[INFO]";
    if (type === "success") prefix = "🫧 [FIZZ]";
    if (type === "warn") prefix = "🥤 [WARN]";
    if (type === "error") prefix = "💥 [SPILL]";
    if (type === "telemetry") prefix = "🛡️ [OTEL]";
    setLogs((prev: string[]) => [...prev, `${timestamp} ${prefix} ${msg}`]);
  };

  const appendSodaLines = (
    lines: ReadonlyArray<{ msg: string; type: "info" | "success" | "warn" | "error" | "telemetry" }>
  ) => {
    lines.forEach((line) => appendLog(line.msg, line.type));
  };

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Initial greeting + live audit tail
  useEffect(() => {
    setLogs([]);
    appendSodaLines(SODA_BOOT_LINES);
    if (broccoli.isDemo) {
      appendLog(`Ready: ${DIETCODE_PITCH.slice(0, 72)}…`, "info");
    } else if (broccoli.health?.message) {
      appendLog(broccoli.health.message, "success");
    }
  }, [broccoli.isDemo, broccoli.health?.message]);

  useEffect(() => {
    if (isDemo || !broccoli.snapshot?.audit?.length) return;
    const lines = broccoli.snapshot.audit.slice(0, 12).map((row) => {
      const ts = new Date(row.timestamp).toISOString().substring(11, 19);
      return `${ts} [${row.type}] ${row.message}`;
    });
    setLogs((prev) => {
      const merged = [...lines.reverse(), ...prev.filter((l) => !l.includes("[hive_"))];
      return merged.slice(0, 80);
    });
  }, [broccoli.snapshot?.audit, isDemo]);

  const openLiveAgent = () => {
    window.location.assign(DIETCODE_LIVE_AGENT_CTA.chatPath);
  };

  return (
    <DietCodeShell className="font-mondwest text-midground normal-case">
      <DietCodeHeader
        liveMode={!isDemo}
        connectionMessage={broccoli.error || broccoli.health?.message || null}
      />

      <DietCodePageNav active={activeTab} onChange={setActiveTab} />

      {activeTab === "home" && (
        <div
          id="dietcode-panel-home"
          role="tabpanel"
          aria-labelledby="dietcode-tab-home"
          className="flex flex-col gap-6"
        >
          <DietCodeSessionBanner
            status={displayStatus}
            onStart={openLiveAgent}
            onReset={() => setSessionStatus("idle")}
            demoMode={isDemo}
          />

          <Card className={CARD_SODA}>
            <CardHeader className="border-b border-current/20 p-3">
              <CardTitle className="text-xs font-bold tracking-wide uppercase normal-case">
                Your progress
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <DietCodeWorkflowStepper status={displayStatus} />
            </CardContent>
          </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* LEFT SIDE: Setup & Session Control Panel */}
          <div className="lg:col-span-1 flex flex-col gap-6">
            
            {/* Target Repository Adapter Setup */}
            <Card className={CARD_SODA}>
              <CardHeader className="border-b border-current/20 p-3">
                <CardTitle className="text-xs font-bold tracking-[0.12em] flex items-center gap-2 uppercase normal-case">
                  <span className="dc-setup-step-badge" aria-hidden>1</span>
                  <Database className="h-3.5 w-3.5 text-primary" />
                  {SETUP_SECTIONS.project.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex flex-col gap-3">
                <p className="dc-section-hint m-0">{SETUP_SECTIONS.project.hint}</p>
                <div>
                  <label className="text-[11px] text-midground/80 block mb-1 font-semibold normal-case">
                    Project name
                  </label>
                  <select
                    className="w-full h-8 px-2 bg-black border border-current/20 text-xs rounded-sm focus:outline-none"
                    value={activeRepo.name}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                      const repo = DETECTED_REPOS.find(r => r.name === e.target.value);
                      if (repo) {
                        setActiveRepo(repo);
                        appendSodaLines([SODA_REPO_SWITCH(repo.name)]);
                      }
                    }}
                    disabled={
                      !isDemo &&
                      sessionStatus !== "idle" &&
                      sessionStatus !== "success" &&
                      sessionStatus !== "reverted"
                    }
                  >
                    {DETECTED_REPOS.map((repo) => (
                      <option key={repo.name} value={repo.name}>
                        {repo.name}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div className="border border-current/10 p-2 bg-black/30">
                    <span className="text-[9px] text-muted-foreground block">Framework</span>
                    <span className="text-xs font-mono font-bold text-primary">{activeRepo.framework}</span>
                  </div>
                  <div className="border border-current/10 p-2 bg-black/30">
                    <span className="text-[9px] text-muted-foreground block">Pkg Manager</span>
                    <span className="text-xs font-mono font-bold text-primary">{activeRepo.packageManager}</span>
                  </div>
                </div>

                <div className="border border-current/10 p-2 bg-black/30">
                  <span className="text-[9px] text-muted-foreground block">Test Runner Command</span>
                  <span className="text-xs font-mono text-muted-foreground block select-all">{activeRepo.testCommand}</span>
                </div>
              </CardContent>
            </Card>

            {/* Bounded Capability Profile */}
            <Card className={CARD_SODA}>
              <CardHeader className="border-b border-current/20 p-3">
                <CardTitle className="text-xs font-bold tracking-[0.12em] flex items-center gap-2 uppercase normal-case">
                  <span className="dc-setup-step-badge" aria-hidden>2</span>
                  <Shield className="h-3.5 w-3.5 text-primary" />
                  {SETUP_SECTIONS.flavor.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex flex-col gap-3">
                <p className="dc-section-hint m-0">{SETUP_SECTIONS.flavor.hint}</p>
                <div>
                  <label className="text-[11px] text-midground/80 block mb-1 font-semibold normal-case">
                    Task type
                  </label>
                  <select
                    className="w-full h-8 px-2 bg-black border border-current/20 text-xs rounded-sm focus:outline-none"
                    value={activeProfile.name}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                      const profile = OPERATOR_PROFILES.find(p => p.name === e.target.value);
                      if (profile) {
                        setActiveProfile(profile);
                        appendSodaLines([SODA_FLAVOR_SWITCH(profile.name)]);
                      }
                    }}
                    disabled={
                      !isDemo &&
                      sessionStatus !== "idle" &&
                      sessionStatus !== "success" &&
                      sessionStatus !== "reverted"
                    }
                  >
                    {OPERATOR_PROFILES.map((p) => {
                      const flavor = OPERATOR_FLAVORS[p.name];
                      return (
                        <option key={p.name} value={p.name}>
                          {flavor
                            ? `${flavor.emoji} ${flavor.friendlyName} — ${flavor.oneLiner}`
                            : p.name}
                        </option>
                      );
                    })}
                  </select>
                </div>

                {OPERATOR_FLAVORS[activeProfile.name] && (
                  <p className="text-[11px] text-primary/90 font-semibold m-0 normal-case">
                    {OPERATOR_FLAVORS[activeProfile.name].emoji}{" "}
                    {OPERATOR_FLAVORS[activeProfile.name].oneLiner}
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground italic leading-relaxed normal-case">
                  {activeProfile.description}
                </p>

                <div className="flex flex-col gap-1 text-[10px] mt-1">
                  <div className="flex justify-between border-b border-current/5 py-1">
                    <span className="text-muted-foreground">Permitted Scope:</span>
                    <span className="font-mono text-primary font-bold">{activeProfile.permittedFiles}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-muted-foreground">Sandbox Constraint:</span>
                    <span className="font-mono text-warning font-bold">{activeProfile.restrictedCommands}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Execution Budget Constraints */}
            <Card className={CARD_SODA}>
              <CardHeader className="border-b border-current/20 p-3">
                <CardTitle className="text-xs font-bold tracking-[0.12em] flex items-center gap-2 uppercase normal-case">
                  <span className="dc-setup-step-badge" aria-hidden>3</span>
                  <Gauge className="h-3.5 w-3.5 text-primary" />
                  {SETUP_SECTIONS.budget.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex flex-col gap-2">
                <p className="dc-section-hint m-0 mb-2">{SETUP_SECTIONS.budget.hint}</p>
                <div className="flex flex-col gap-2 text-[10px]">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Max Mutated Files</span>
                    <span className="font-mono font-bold">{budgetLimit.maxFiles} files</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Max Runtime Duration</span>
                    <span className="font-mono font-bold">{budgetLimit.maxRuntimeMinutes} mins</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Max Safe Tool Calls</span>
                    <span className="font-mono font-bold">{budgetLimit.maxToolCalls} calls</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Max Patch Size Limit</span>
                    <span className="font-mono font-bold">{budgetLimit.maxPatchSize} bytes</span>
                  </div>
                </div>
                
                {displayStatus !== "idle" && (
                  <div className="border-t border-current/10 pt-3 mt-2 flex flex-col gap-2">
                    <span className="text-[9px] text-primary font-bold">
                      {isDemo ? "Example budget (illustrative):" : "Active Runtime Budget Consumed:"}
                    </span>
                    <div className="flex flex-col gap-1.5 text-[10px]">
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Files Edited</span>
                          <span>{displayBudgetUsage.files} / {budgetLimit.maxFiles}</span>
                        </div>
                        <div className="w-full dc-progress-fizz h-1.5 border border-current/10 rounded-full overflow-hidden">
                          <div
                            className="h-full transition-all duration-300"
                            style={{ width: `${(displayBudgetUsage.files / budgetLimit.maxFiles) * 100}%` }}
                          />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Tool Calls</span>
                          <span>{displayBudgetUsage.toolCalls} / {budgetLimit.maxToolCalls}</span>
                        </div>
                        <div className="w-full dc-progress-fizz h-1.5 border border-current/10 rounded-full overflow-hidden">
                          <div
                            className="h-full transition-all duration-300"
                            style={{ width: `${(displayBudgetUsage.toolCalls / budgetLimit.maxToolCalls) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* RIGHT: proposal, diff, logs */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            {displayStatus !== "idle" && (
              <div className="flex flex-wrap gap-3 text-[10px] normal-case tracking-normal px-1 text-midground/65">
                <span>
                  Worker:{" "}
                  <strong className="text-midground">
                    {displayStatus === "proposed"
                      ? "Paused — waiting for you"
                      : "Running"}
                  </strong>
                </span>
                <span>
                  Checkpoints saved:{" "}
                  <strong className="text-midground">{isDemo ? 0 : wakeupsCount}</strong>
                </span>
                {isDemo ? (
                  <span className="text-warning/90">Example UI only — not connected to BroccoliDB</span>
                ) : broccoli.snapshot?.shard_id ? (
                  <span className="text-success/90">Shard: {broccoli.snapshot.shard_id}</span>
                ) : null}
              </div>
            )}

            {/* Proposed changes — review before approve */}
            {displayStatus !== "idle" && displayStatus !== "preflight" && (
              <Card className={CARD_SODA}>
                <CardHeader className="border-b border-current/20 p-3">
                  <CardTitle className="text-xs font-bold tracking-[0.12em] flex items-center gap-2 uppercase normal-case">
                    <FileText className="h-3.5 w-3.5 text-primary" />
                    Proposed changes — review before you approve
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 flex flex-col gap-4">
                  
                  {/* Proposal Metadata */}
                  <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-black/40 p-3 border border-current/10 rounded-sm">
                    <div>
                      <span className="text-muted-foreground block">Proposed mutation path:</span>
                      <span className="text-primary font-bold select-all">
                        {pendingProposal
                          ? pendingProposal.violation_id || pendingProposal.id
                          : MOCK_DIFFS[activeProfile.name]?.path}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Proposal status:</span>
                      <span className="text-muted-foreground block select-all">
                        {pendingProposal?.status ?? (isDemo ? "cf2390a1b2c3d4e5f6..." : "—")}
                      </span>
                    </div>
                    <div className="border-t border-current/5 pt-2 mt-2">
                      <span className="text-muted-foreground block">Violation:</span>
                      <span className="text-primary font-bold text-[9px] truncate block select-all">
                        {pendingProposal?.violation ?? argsHash}
                      </span>
                    </div>
                    <div className="border-t border-current/5 pt-2 mt-2">
                      <span className="text-muted-foreground block">Rationale:</span>
                      <span className="text-primary font-bold text-[9px] truncate block select-all">
                        {pendingProposal?.rationale ?? policyHash}
                      </span>
                    </div>
                  </div>

                  {/* Diff Canvas */}
                  <div className="border border-current/25 rounded-sm overflow-hidden bg-black font-mono text-[11px] leading-relaxed">
                    <div className="bg-background-base/80 px-3 py-2 border-b border-current/15 text-[10px] text-muted-foreground flex justify-between">
                      <span>{pendingProposal ? "Healing proposal" : "Unified Diff Preview"}</span>
                      <span className="text-primary font-bold">
                        {pendingProposal?.id ?? MOCK_DIFFS[activeProfile.name]?.path}
                      </span>
                    </div>
                    <pre className="p-3 overflow-x-auto whitespace-pre leading-relaxed text-muted-foreground max-h-60">
                      {(pendingProposal?.proposed_code ?? MOCK_DIFFS[activeProfile.name]?.diff)
                        .split("\n")
                        .map((line, idx) => {
                        let lineStyle = "text-muted-foreground";
                        if (line.startsWith("+")) lineStyle = "text-success bg-success/5 font-bold";
                        if (line.startsWith("-")) lineStyle = "text-destructive bg-destructive/5 font-bold";
                        if (line.startsWith("@@")) lineStyle = "text-primary bg-primary/5 font-bold";
                        return (
                          <div key={idx} className={`px-2 py-0.5 ${lineStyle}`}>
                            {line}
                          </div>
                        );
                      })}
                    </pre>
                  </div>

                  {/* GCS Snapshot Checkpoints list */}
                  <div className="border border-current/10 p-3 rounded-sm bg-black/30 flex flex-col gap-2">
                    <span className="text-[10px] text-muted-foreground font-bold flex items-center gap-1.5">
                      <Database className="h-3 w-3 text-primary" />
                      Durable Snapshot Checkpoints (gs://operator-artifacts/):
                    </span>
                    <div className="grid grid-cols-3 gap-2 text-[9px] font-mono">
                      <div className="flex items-center justify-between border border-current/10 p-2 bg-black/40">
                        <span>pre-mutation.tar.gz</span>
                        <Download className="h-3 w-3 text-primary" />
                      </div>
                      <div className={`flex items-center justify-between border border-current/10 p-2 ${displayStatus !== "proposed" && displayStatus !== "applying" ? "bg-black/40" : "opacity-30"}`}>
                        <span>post-mutation.tar.gz</span>
                        <Download className="h-3 w-3 text-primary opacity-40" aria-hidden />
                      </div>
                      <div className={`flex items-center justify-between border border-current/10 p-2 ${displayStatus === "success" ? "bg-black/40" : "opacity-30"}`}>
                        <span>post-test.tar.gz</span>
                        <Download className="h-3 w-3 text-primary opacity-40" aria-hidden />
                      </div>
                    </div>
                  </div>

                  {isDemo && displayStatus === "proposed" && (
                    <div className="flex flex-col gap-3 border-t border-current/15 pt-4">
                      <p className="text-[11px] text-midground/75 m-0 leading-relaxed normal-case">
                        {DIETCODE_LIVE_AGENT_CTA.hint} Approve/reject flows through Dashboard → Chat until BroccoliDB is initialized.
                      </p>
                      <Button asChild className="h-9 px-4 text-xs font-bold dc-btn-primary normal-case tracking-normal">
                        <Link to={DIETCODE_LIVE_AGENT_CTA.chatPath}>
                          <ExternalLink className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                          {DIETCODE_LIVE_AGENT_CTA.label}
                        </Link>
                      </Button>
                    </div>
                  )}

                  {!isDemo && pendingProposal && displayStatus === "proposed" && (
                    <div className="flex flex-wrap gap-2 border-t border-current/15 pt-4">
                      <Button
                        className="h-9 px-4 text-xs font-bold dc-btn-primary normal-case tracking-normal"
                        onClick={() => void broccoli.approveProposal(pendingProposal.id)}
                      >
                        <Check className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                        Approve proposal
                      </Button>
                      <Button
                        className="h-9 px-4 text-xs font-semibold bg-black/50 border border-current/20 normal-case tracking-normal"
                        onClick={() => void broccoli.denyProposal(pendingProposal.id)}
                      >
                        <X className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                        Deny
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Observability Terminal Log Panel */}
            <Card className={CARD_SODA}>
              <CardHeader className="border-b border-current/20 p-3">
                <CardTitle className="text-xs font-bold tracking-[0.12em] flex items-center gap-2 uppercase normal-case">
                  <Terminal className="h-3.5 w-3.5 text-primary" />
                  {isDemo ? "Example activity log" : "Live activity (this session)"}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3">
                <pre className="bg-black/95 p-3 border border-current/25 rounded-sm font-mono text-[10px] text-muted-foreground leading-relaxed h-48 overflow-y-auto whitespace-pre-wrap break-all">
                  {logs.map((log: string, idx: number) => {
                    let logStyle = "text-muted-foreground dc-log-line";
                    if (log.includes("🫧") || log.includes("FIZZ")) {
                      logStyle = "text-success font-bold dc-log-line dc-log-line--fizz";
                    } else if (log.includes("🥤") || log.includes("WARN")) {
                      logStyle = "text-warning font-bold dc-log-line";
                    } else if (log.includes("💥") || log.includes("SPILL")) {
                      logStyle = "text-destructive font-bold dc-log-line";
                    }
                    return (
                      <div key={idx} className={logStyle}>
                        {log}
                      </div>
                    );
                  })}
                  <div ref={terminalEndRef} />
                </pre>
              </CardContent>
            </Card>

          </div>

        </div>
        </div>
      )}

      {activeTab === "quality" && (
        <div
          id="dietcode-panel-quality"
          role="tabpanel"
          aria-labelledby="dietcode-tab-quality"
        >
        <Card className={CARD_SODA}>
          <CardHeader className="border-b border-current/20 p-4 flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base font-bold flex items-center gap-2 uppercase tracking-wide">
                <TrendingUp className="h-5 w-5 text-primary" />
                Automated quality checks
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5 normal-case tracking-normal">
                {isDemo
                  ? "Sample metrics for layout preview. Run real checks from the live agent terminal."
                  : broccoli.snapshot?.graph
                    ? `Live graph: ${broccoli.snapshot.graph.nodes} nodes · ${broccoli.snapshot.graph.edges} edges · ${broccoli.snapshot.graph.db_size_mb} MB`
                    : "BroccoliDB graph metrics when database is initialized."}
              </p>
            </div>

            {isDemo ? (
              <Button asChild className="h-8 px-4 text-xs font-bold dc-btn-primary shrink-0">
                <Link to={DIETCODE_LIVE_AGENT_CTA.chatPath}>
                  <ExternalLink className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                  {DIETCODE_LIVE_AGENT_CTA.label}
                </Link>
              </Button>
            ) : null}
          </CardHeader>
          <CardContent className="p-4 flex flex-col gap-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Graph nodes</span>
                <span className="text-xl font-bold font-mono text-primary">
                  {isDemo ? 4 : (broccoli.snapshot?.graph?.nodes ?? 0)}
                </span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Queue jobs</span>
                <span className="text-xl font-bold font-mono text-success">
                  {isDemo ? "100%" : (broccoli.snapshot?.queue?.total ?? 0)}
                </span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Hive sessions</span>
                <span className="text-xl font-bold font-mono text-warning">
                  {isDemo ? "0%" : (broccoli.snapshot?.sessions?.length ?? 0)}
                </span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Proposals</span>
                <span className="text-xl font-bold font-mono text-primary">
                  {isDemo ? "4.2s" : (broccoli.snapshot?.proposals?.length ?? 0)}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-bold">Standard Suite Scenarios (sample):</span>
              <div className="border border-current/15 rounded-sm overflow-hidden bg-black/30">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="bg-background-base/80 text-[10px] border-b border-current/20">
                      <th className="p-3">Scenario Name</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Worker Time</th>
                      <th className="p-3">Estimated Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { name: "fix failing test", status: "passed", duration: "3.2s", cost: "$0.0021" },
                      { name: "rename symbol", status: "passed", duration: "4.8s", cost: "$0.0034" },
                      { name: "upgrade vitest devDependency", status: "passed", duration: "5.1s", cost: "$0.0019" },
                      { name: "add types for spine session", status: "passed", duration: "3.9s", cost: "$0.0028" },
                    ].map((bench, idx) => (
                      <tr key={idx} className="border-b border-current/5">
                        <td className="p-3 font-bold text-midground">{bench.name}</td>
                        <td className="p-3">
                          <Badge tone="success" className="text-[9px]">
                            {bench.status}
                          </Badge>
                        </td>
                        <td className="p-3 text-muted-foreground">{bench.duration}</td>
                        <td className="p-3 text-primary">{bench.cost}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>
        </div>
      )}

      {activeTab === "activity" && (
        <div
          id="dietcode-panel-activity"
          role="tabpanel"
          aria-labelledby="dietcode-tab-activity"
        >
        <Card className={CARD_SODA}>
          <CardHeader className="border-b border-current/20 p-4">
            <CardTitle className="text-base font-bold flex items-center gap-2 uppercase tracking-wide">
              <Activity className="h-5 w-5 text-primary" />
              System activity & metrics
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5 normal-case tracking-normal">
              {isDemo
                ? "Sample telemetry for layout preview only — not live OpenTelemetry."
                : broccoli.snapshot?.audit?.length
                  ? "Live hive_audit tail from BroccoliDB."
                  : "Initialize BroccoliDB to stream hive audit events here."}
            </p>
          </CardHeader>
          <CardContent className="p-4 flex flex-col gap-4 font-mono text-xs">
            <div className="grid grid-cols-2 gap-4">
              <div className="border border-current/10 p-3 bg-black/40 rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">BroccoliDB shard</span>
                <span className="text-sm font-bold text-primary">
                  {isDemo ? "demo" : (broccoli.snapshot?.shard_id ?? "—")}
                </span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Queue pending</span>
                <span className="text-sm font-bold text-primary">
                  {isDemo
                    ? "120 ms"
                    : (broccoli.snapshot?.queue?.by_status?.pending ?? 0)}
                </span>
              </div>
            </div>
            <div className="bg-black p-3 border border-current/25 rounded-sm font-mono text-[10px] text-muted-foreground h-64 overflow-y-auto leading-relaxed">
              {isDemo ? (
                <>
                  <div className="text-primary font-bold">&gt; tail -f open-telemetry-spans.json</div>
                  <div className="text-success mt-1">{"{\"span_id\":\"s-a42d\",\"name\":\"SecretManager.FetchKey\",\"duration_ms\":84,\"status\":\"ok\"}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-ef90\",\"name\":\"CloudTasks.EnqueueJob\",\"duration_ms\":145,\"status\":\"ok\",\"payload\":{\"queue\":\"operator-job-queue\"}}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-b2c1\",\"name\":\"WorkerRuntime.RepoSafetyCheck\",\"duration_ms\":230,\"status\":\"ok\",\"payload\":{\"repo\":\"diet-hermes\"}}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-f1a2\",\"name\":\"GCS.UploadSnapshot\",\"duration_ms\":512,\"status\":\"ok\",\"payload\":{\"path\":\"recovery/pre-mutation.tar.gz\"}}"}</div>
                  <div className="text-warning">{"{\"span_id\":\"s-a12b\",\"name\":\"WorkerRuntime.Exited\",\"payload\":{\"status\":\"checkpoint_saved\",\"reason\":\"waiting_for_approval\"}}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-d3e4\",\"name\":\"ControlPlane.ApprovalGateMatched\",\"duration_ms\":12,\"status\":\"ok\"}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-9c8d\",\"name\":\"WorkerRuntime.ApplyChanges\",\"duration_ms\":98,\"status\":\"ok\"}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-e3f4\",\"name\":\"WorkerRuntime.ExecuteTests\",\"duration_ms\":840,\"status\":\"ok\",\"payload\":{\"exit_code\":0}}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-7a8b\",\"name\":\"GCS.UploadSnapshot\",\"duration_ms\":480,\"status\":\"ok\",\"payload\":{\"path\":\"recovery/post-test.tar.gz\"}}"}</div>
                  <div className="text-success">{"{\"span_id\":\"s-2c3d\",\"name\":\"WorkerRuntime.CleanWorkspace\",\"duration_ms\":45,\"status\":\"ok\"}"}</div>
                  <div className="text-primary font-bold mt-2">&gt; tail -f stdout.log</div>
                  <div className="mt-1">12:04:12 [INFO] Control Plane API enqueued job.</div>
                  <div>12:04:13 [INFO] Spawned Worker Runtime container instance.</div>
                  <div>12:04:15 [SUCCESS] Workspace Check safety policy passed.</div>
                  <div>12:04:16 [WARN] Worker Exited. Recovery state synchronized in GCS.</div>
                </>
              ) : (
                (broccoli.snapshot?.audit ?? []).map((row) => (
                  <div key={row.id} className="text-success">
                    {new Date(row.timestamp).toISOString().substring(11, 19)} [{row.type}] {row.message}
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
        </div>
      )}

    </DietCodeShell>
  );
}
