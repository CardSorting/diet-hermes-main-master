import { useState, useEffect, useRef } from "react";
import {
  Shield,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  Play,
  Check,
  X,
  FileText,
  Database,
  Download,
  TrendingUp,
  Activity,
  Gauge,
  History,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
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
  DIETCODE_PITCH,
  SODA_APPROVE_LINES,
  SODA_APPLY_SUCCESS,
  SODA_BOOT_LINES,
  SODA_CANCEL,
  SODA_FLAVOR_SWITCH,
  SODA_REPO_SWITCH,
  SODA_SESSION_START,
  SODA_SPILL_LINES,
  SODA_TELEMETRY_LINES,
  type DietCodeTabId,
  type SessionStatus,
} from "@/components/dietcode";

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

export default function DietCodePage() {
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

  // State flags for interactive workflow
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");
  const [activeTab, setActiveTab] = useState<DietCodeTabId>("home");
  const [logs, setLogs] = useState<string[]>([]);
  const [wakeupsCount, setWakeupsCount] = useState(0);
  const [budgetUsage, setBudgetUsage] = useState({
    files: 0,
    runtime: 0,
    toolCalls: 0,
    patchSize: 0,
    testRuntime: 0,
  });

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

  // Initial greeting
  useEffect(() => {
    setLogs([]);
    appendSodaLines(SODA_BOOT_LINES);
    appendLog(`Ready: ${DIETCODE_PITCH.slice(0, 72)}…`, "info");
  }, []);

  // Handler: Start Operator Session
  const handleStartSession = () => {
    setSessionStatus("preflight");
    setLogs([]);
    setWakeupsCount(0);
    setBudgetUsage({ files: 0, runtime: 0, toolCalls: 0, patchSize: 0, testRuntime: 0 });
    
    appendSodaLines([SODA_REPO_SWITCH(activeRepo.name)]);
    appendLog(`Framework: ${activeRepo.framework} · profile ${activeProfile.name}`, "info");

    setTimeout(() => {
      appendSodaLines(SODA_SESSION_START);
      setBudgetUsage((prev: { files: number; runtime: number; toolCalls: number; patchSize: number; testRuntime: number }) => ({ ...prev, files: 1, toolCalls: 3, runtime: 1 }));
      setSessionStatus("proposed");
      appendLog("Pre-mutation snapshot canned (12.4 MB) → gs://operator-artifacts/recovery/", "success");
    }, 1500);
  };

  // Handler: Approve and Apply Changes
  const handleApprove = () => {
    setSessionStatus("applying");
    appendSodaLines(SODA_APPROVE_LINES);
    appendLog(`Args hash verified [${argsHash.substring(0, 12)}…]`, "success");
    setWakeupsCount(1);

    setTimeout(() => {
      appendLog("Worker respawned from GCS checkpoint — workspace reconstituted.", "success");
      appendLog("Pouring approved changes into the workspace…", "info");
      
      const fileCount = activeProfile.name === "TypingOperator" ? 1 : 2;
      const patchLen = activeProfile.name === "TestFixOperator" ? 450 : 280;
      setBudgetUsage((prev: { files: number; runtime: number; toolCalls: number; patchSize: number; testRuntime: number }) => ({
        ...prev,
        files: fileCount,
        toolCalls: prev.toolCalls + 4,
        patchSize: patchLen,
        runtime: prev.runtime + 2,
      }));

      setSessionStatus("testing");
      appendLog(`Test shaker: "${activeRepo.testCommand}"`, "info");

      setTimeout(() => {
        appendSodaLines(SODA_APPLY_SUCCESS);
        setBudgetUsage((prev: { files: number; runtime: number; toolCalls: number; patchSize: number; testRuntime: number }) => ({ ...prev, testRuntime: 1, runtime: prev.runtime + 1 }));
        setSessionStatus("success");
        appendLog(`Bounded session flat-out success in ~${budgetUsage.runtime + 3} min.`, "success");
      }, 1500);

    }, 1500);
  };

  // Handler: Trigger Policy Budget Violation Simulation
  const handleTriggerViolation = () => {
    setSessionStatus("applying");
    appendLog("Control Plane: Resuming worker execution...", "info");
    
    setTimeout(() => {
      appendLog("Worker Runtime: Respawned worker container.", "success");
      appendLog("Worker Runtime: Applying out-of-bounds file write proposal...", "warn");
      appendLog("Worker Runtime: Checking constraints...", "info");
      
      // Simulate exceeding files budget
      setBudgetUsage((prev: { files: number; runtime: number; toolCalls: number; patchSize: number; testRuntime: number }) => ({
        ...prev,
        files: 15, // Over limit
        toolCalls: 30, // Over limit
        patchSize: 6500, // Over limit
      }));

      setSessionStatus("violation");
      appendSodaLines(SODA_SPILL_LINES);
      appendLog("Budget: max 10 files, attempted 15.", "error");

      setTimeout(() => {
        setSessionStatus("reverted");
        appendLog("Rollback poured — workspace restored.", "success");
      }, 1000);

    }, 1200);
  };

  // Golden Benchmarks Simulation State
  const [benchStats, setBenchStats] = useState({
    running: false,
    completed: false,
    successRate: 100,
    rollbackRate: 0,
    avgDurationSec: 4.2,
    totalRuns: 4,
    benchmarks: [
      { name: "fix failing test", status: "passed", duration: "3.2s", cost: "$0.0021" },
      { name: "rename symbol", status: "passed", duration: "4.8s", cost: "$0.0034" },
      { name: "upgrade vitest devDependency", status: "passed", duration: "5.1s", cost: "$0.0019" },
      { name: "add types for spine session", status: "passed", duration: "3.9s", cost: "$0.0028" },
    ]
  });

  const runGoldenSuite = () => {
    setBenchStats((prev: { running: boolean; completed: boolean; successRate: number; rollbackRate: number; avgDurationSec: number; totalRuns: number; benchmarks: Array<{ name: string; status: string; duration: string; cost: string }> }) => ({ ...prev, running: true, completed: false }));
    appendLog("Golden pour suite — shaking 250 operators…", "info");

    setTimeout(() => {
      setBenchStats((prev: { running: boolean; completed: boolean; successRate: number; rollbackRate: number; avgDurationSec: number; totalRuns: number; benchmarks: Array<{ name: string; status: string; duration: string; cost: string }> }) => ({
        ...prev,
        running: false,
        completed: true,
        successRate: 98.4,
        rollbackRate: 1.6,
        avgDurationSec: 4.1,
        totalRuns: 250,
      }));
      appendLog(SODA_TELEMETRY_LINES[0], "success");
      appendLog(SODA_TELEMETRY_LINES[1], "telemetry");
    }, 2000);
  };

  return (
    <DietCodeShell className="font-mondwest text-midground normal-case">
      <DietCodeHeader />

      <DietCodePageNav active={activeTab} onChange={setActiveTab} />

      {activeTab === "home" && (
        <div
          id="dietcode-panel-home"
          role="tabpanel"
          aria-labelledby="dietcode-tab-home"
          className="flex flex-col gap-6"
        >
          <DietCodeSessionBanner
            status={sessionStatus}
            onStart={handleStartSession}
            onReset={() => setSessionStatus("idle")}
          />

          <Card className={CARD_SODA}>
            <CardHeader className="border-b border-current/20 p-3">
              <CardTitle className="text-xs font-bold tracking-wide uppercase normal-case">
                Your progress
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <DietCodeWorkflowStepper status={sessionStatus} />
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
                    disabled={sessionStatus !== "idle" && sessionStatus !== "success" && sessionStatus !== "reverted"}
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
                    disabled={sessionStatus !== "idle" && sessionStatus !== "success" && sessionStatus !== "reverted"}
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
                
                {sessionStatus !== "idle" && (
                  <div className="border-t border-current/10 pt-3 mt-2 flex flex-col gap-2">
                    <span className="text-[9px] text-primary font-bold">Active Runtime Budget Consumed:</span>
                    <div className="flex flex-col gap-1.5 text-[10px]">
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Files Edited</span>
                          <span>{budgetUsage.files} / {budgetLimit.maxFiles}</span>
                        </div>
                        <div className="w-full dc-progress-fizz h-1.5 border border-current/10 rounded-full overflow-hidden">
                          <div
                            className="h-full transition-all duration-300"
                            style={{ width: `${(budgetUsage.files / budgetLimit.maxFiles) * 100}%` }}
                          />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Tool Calls</span>
                          <span>{budgetUsage.toolCalls} / {budgetLimit.maxToolCalls}</span>
                        </div>
                        <div className="w-full dc-progress-fizz h-1.5 border border-current/10 rounded-full overflow-hidden">
                          <div
                            className="h-full transition-all duration-300"
                            style={{ width: `${(budgetUsage.toolCalls / budgetLimit.maxToolCalls) * 100}%` }}
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
            {sessionStatus !== "idle" && (
              <div className="flex flex-wrap gap-3 text-[10px] normal-case tracking-normal px-1 text-midground/65">
                <span>
                  Worker:{" "}
                  <strong className="text-midground">
                    {sessionStatus === "proposed"
                      ? "Paused — waiting for you"
                      : "Running"}
                  </strong>
                </span>
                <span>
                  Checkpoints saved: <strong className="text-midground">{wakeupsCount}</strong>
                </span>
              </div>
            )}

            {/* Proposed changes — review before approve */}
            {sessionStatus !== "idle" && sessionStatus !== "preflight" && (
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
                      <span className="text-primary font-bold select-all">{MOCK_DIFFS[activeProfile.name]?.path}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Target Commit SHA:</span>
                      <span className="text-muted-foreground block select-all">cf2390a1b2c3d4e5f6...</span>
                    </div>
                    <div className="border-t border-current/5 pt-2 mt-2">
                      <span className="text-muted-foreground block">Mandatory argsHash:</span>
                      <span className="text-primary font-bold text-[9px] truncate block select-all">{argsHash}</span>
                    </div>
                    <div className="border-t border-current/5 pt-2 mt-2">
                      <span className="text-muted-foreground block">Mandatory policyHash:</span>
                      <span className="text-primary font-bold text-[9px] truncate block select-all">{policyHash}</span>
                    </div>
                  </div>

                  {/* Diff Canvas */}
                  <div className="border border-current/25 rounded-sm overflow-hidden bg-black font-mono text-[11px] leading-relaxed">
                    <div className="bg-background-base/80 px-3 py-2 border-b border-current/15 text-[10px] text-muted-foreground flex justify-between">
                      <span>Unified Diff Preview</span>
                      <span className="text-primary font-bold">{MOCK_DIFFS[activeProfile.name]?.path}</span>
                    </div>
                    <pre className="p-3 overflow-x-auto whitespace-pre leading-relaxed text-muted-foreground max-h-60">
                      {MOCK_DIFFS[activeProfile.name]?.diff.split("\n").map((line, idx) => {
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
                      <div className={`flex items-center justify-between border border-current/10 p-2 ${sessionStatus !== "proposed" && sessionStatus !== "applying" ? "bg-black/40" : "opacity-30"}`}>
                        <span>post-mutation.tar.gz</span>
                        <Download className="h-3 w-3 text-primary" />
                      </div>
                      <div className={`flex items-center justify-between border border-current/10 p-2 ${sessionStatus === "success" ? "bg-black/40" : "opacity-30"}`}>
                        <span>post-test.tar.gz</span>
                        <Download className="h-3 w-3 text-primary" />
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  {sessionStatus === "proposed" && (
                    <div className="flex flex-col sm:flex-row gap-3 border-t border-current/15 pt-4">
                      <Button
                        onClick={handleApprove}
                        className="flex-1 h-9 px-4 text-xs font-bold tracking-widest bg-success text-black hover:bg-success/80"
                      >
                        <Check className="mr-1.5 h-3.5 w-3.5" />
                        Approve & apply
                      </Button>
                      
                      <Button
                        onClick={handleTriggerViolation}
                        className="flex-1 h-9 px-4 text-xs font-bold tracking-widest bg-warning text-black hover:bg-warning/80"
                      >
                        <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                        Test safety limit (demo)
                      </Button>

                      <Button
                        onClick={() => {
                          setSessionStatus("idle");
                          appendSodaLines([SODA_CANCEL()]);
                        }}
                        className="h-9 px-4 text-xs font-bold tracking-widest bg-transparent border border-current/20 text-destructive hover:bg-destructive/5"
                      >
                        <X className="mr-1.5 h-3.5 w-3.5" />
                        Reject
                      </Button>
                    </div>
                  )}

                  {/* Active applying states */}
                  {sessionStatus === "applying" && (
                    <div className="flex items-center justify-center py-6 gap-3 border-t border-current/15">
                      <Spinner className="text-primary text-xl" />
                      <span className="text-xs font-bold animate-pulse text-primary">Control Plane: Enqueuing task to wake up worker container...</span>
                    </div>
                  )}

                  {sessionStatus === "testing" && (
                    <div className="flex flex-col gap-2 border-t border-current/15 pt-4">
                      <div className="flex items-center justify-center py-3 gap-3">
                        <Spinner className="text-primary text-lg" />
                        <span className="text-xs font-bold animate-pulse text-primary">Worker Runtime: Running test suite command: "{activeRepo.testCommand}"</span>
                      </div>
                      <div className="bg-black p-3 border border-current/20 rounded-sm font-mono text-[10px] text-success overflow-x-auto leading-relaxed max-h-32">
                        <div>&gt; {activeRepo.testCommand}</div>
                        <div className="text-muted-foreground mt-1">RUNS  src/__tests__/spine.test.ts</div>
                        <div>✓ should enforce Bounded Operator pipeline constraints (12ms)</div>
                        <div>✓ should enforce strict hash binding for alpha (8ms)</div>
                        <div className="text-success font-bold mt-1">Test Suites: 1 passed, 1 total</div>
                        <div className="text-success font-bold">Tests:       2 passed, 2 total</div>
                        <div className="text-success font-bold">Snapshots:   0 total</div>
                        <div className="text-muted-foreground">Time:        0.84s</div>
                      </div>
                    </div>
                  )}

                  {/* Success State */}
                  {sessionStatus === "success" && (
                    <div className="border border-success/30 bg-success/5 p-4 rounded-sm flex flex-col gap-2">
                      <span className="text-xs font-bold text-success flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-success" />
                        Operator Changes Applied & Tested Successfully!
                      </span>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        The single-use Worker Runtime container has successfully run your test suite, uploaded the final post-test workspace snapshot, and terminated cleanly. All mutations are durably written.
                      </p>
                    </div>
                  )}

                  {/* Violation Simulation State */}
                  {sessionStatus === "violation" && (
                    <div className="border border-destructive/30 bg-destructive/5 p-4 rounded-sm flex flex-col gap-2">
                      <span className="text-xs font-bold text-destructive flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-destructive" />
                        BUDGET VIOLATION DETECTED!
                      </span>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        The active worker exceeded the Mutated Files threshold limit of 10 (mutated 15 files). Executing automatic workspace recovery rollback protocol instantly...
                      </p>
                    </div>
                  )}

                  {/* Reverted State */}
                  {sessionStatus === "reverted" && (
                    <div className="border border-warning/30 bg-warning/5 p-4 rounded-sm flex flex-col gap-2">
                      <span className="text-xs font-bold text-warning flex items-center gap-2">
                        <History className="h-4 w-4 text-warning" />
                        Rollback Audit Recovery Succeeded
                      </span>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        The volatile workspace has been completely restored to git commit checkout base `cf2390a` using the GCS `pre-mutation.tar.gz` recovery snapshot. Parity validated.
                      </p>
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
                  Live activity (this session)
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
          <CardHeader className="border-b border-current/20 p-4 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold flex items-center gap-2 uppercase tracking-wide">
                <TrendingUp className="h-5 w-5 text-primary" />
                Automated quality checks
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5 normal-case tracking-normal">
                See how often proposed changes pass tests and stay within safety limits—like a taste test for your codebase.
              </p>
            </div>
            
            <Button
              onClick={runGoldenSuite}
              disabled={benchStats.running}
              className="h-8 px-4 text-xs font-bold dc-btn-primary"
            >
              {benchStats.running ? (
                <>
                  <Spinner className="mr-1.5" />
                  Running checks…
                </>
              ) : (
                <>
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                  Run all checks
                </>
              )}
            </Button>
          </CardHeader>
          <CardContent className="p-4 flex flex-col gap-6">
            
            {/* Stats Overview */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Total Operators Run</span>
                <span className="text-xl font-bold font-mono text-primary">{benchStats.totalRuns}</span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Success Rate</span>
                <span className="text-xl font-bold font-mono text-success">{benchStats.successRate}%</span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Rollback Rate</span>
                <span className="text-xl font-bold font-mono text-warning">{benchStats.rollbackRate}%</span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 text-center rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Avg Exec Time</span>
                <span className="text-xl font-bold font-mono text-primary">{benchStats.avgDurationSec}s</span>
              </div>
            </div>

            {/* Benchmarks List */}
            <div className="flex flex-col gap-2">
              <span className="text-xs font-bold">Standard Suite Scenarios:</span>
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
                    {benchStats.benchmarks.map((bench: { name: string; status: string; duration: string; cost: string }, idx: number) => (
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
            
            {benchStats.completed && (
              <div className="border border-success/20 bg-success/5 p-4 rounded-sm flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-success shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold text-success">Golden Regressions Validation Succeeded!</span>
                  <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                    Zero regressions detected. The single-node operator workspace boundary safely isolated and completed all mutations, verifying full consistency under concurrent load tests.
                  </p>
                </div>
              </div>
            )}
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
              Technical traces for operators and engineers—latency, costs, and background job health.
            </p>
          </CardHeader>
          <CardContent className="p-4 flex flex-col gap-4 font-mono text-xs">
            <div className="grid grid-cols-2 gap-4">
              <div className="border border-current/10 p-3 bg-black/40 rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Cloud Run Execution Cost</span>
                <span className="text-sm font-bold text-primary">$0.0034 / turn</span>
              </div>
              <div className="border border-current/10 p-3 bg-black/40 rounded-sm">
                <span className="text-[10px] text-muted-foreground block uppercase">Task Queue Latency</span>
                <span className="text-sm font-bold text-primary">120 ms</span>
              </div>
            </div>
            <div className="bg-black p-3 border border-current/25 rounded-sm font-mono text-[10px] text-muted-foreground h-64 overflow-y-auto leading-relaxed">
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
            </div>
          </CardContent>
        </Card>
        </div>
      )}

    </DietCodeShell>
  );
}
