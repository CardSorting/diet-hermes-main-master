export type FirebaseRuntimeEventType =
  | "session.ready"
  | "user.prompt"
  | "stream.transcript"
  | "stream.thinking"
  | "proposal.plan"
  | "proposal.patch"
  | "proposal.command"
  | "approval.request"
  | "approval.response"
  | "execution.result"
  | "execution.error"
  | "session.error"
  | "session.complete"
  | "context.snapshot"
  | "context.request"
  | "context.response";

export interface FirebaseRuntimeEvent {
  eventId: string;
  sessionId: string;
  workspaceId: string;
  type: FirebaseRuntimeEventType;
  source: "local-client" | "remote-runtime" | "firebase-function";
  createdAt: unknown;
  payload: Record<string, unknown>;
}

export interface FirebaseSessionDocument {
  sessionId: string;
  workspaceId: string;
  uid: string;
  status: "active" | "completed" | "error";
  mode: "firebase";
  createdAt: unknown;
  updatedAt: unknown;
  client: {
    type: string;
    version: string;
    platform: string;
  };
  workspace: FirebaseWorkspaceMetadata;
}

export interface FirebaseWorkspaceMetadata {
  workspaceId: string;
  rootName: string;
  gitBranch?: string;
  gitHead?: string;
  dirty: boolean;
}

export interface PlanProposal {
  proposalId: string;
  type: "proposal.plan";
  status: "pending_approval" | "approved" | "denied" | "executing" | "completed" | "failed";
  summary: string;
  steps: string[];
  createdAt: unknown;
}

export interface PatchProposal {
  proposalId: string;
  type: "proposal.patch";
  status: "pending_approval" | "approved" | "denied" | "executing" | "completed" | "failed";
  riskLevel: "low" | "medium" | "high";
  summary: string;
  reason: string;
  files: Array<{
    path: string;
    diff: string;
  }>;
  createdAt: unknown;
}

export interface CommandProposal {
  proposalId: string;
  type: "proposal.command";
  status: "pending_approval" | "approved" | "denied" | "executing" | "completed" | "failed";
  riskLevel: "low" | "medium" | "high";
  command: string;
  cwd: string;
  reason: string;
  createdAt: unknown;
}

export interface ApprovalRecord {
  approvalId: string;
  proposalId: string;
  decision: "approved" | "denied";
  approvedBy: "local-human";
  createdAt: unknown;
}

export interface ExecutionResultRecord {
  executionId: string;
  proposalId: string;
  type: "patch.apply" | "command.run";
  success: boolean;
  filesChanged?: string[];
  stdout?: string;
  stderr?: string;
  createdAt: unknown;
}

export interface LocalAuditEntry {
  timestamp: string;
  action: string;
  proposalId?: string;
  success: boolean;
  details: Record<string, unknown>;
}

// Phase 9: Context Sync Types
export interface ContextFile {
  path: string;
  content: string;
  truncated: boolean;
}

export interface ContextGitStatus {
  branch: string;
  head: string;
  dirty: boolean;
}

export interface ContextSnapshot {
  contextId: string;
  sessionId: string;
  prompt: string;
  git: ContextGitStatus;
  visibleFiles: ContextFile[];
  createdAt: unknown;
}

export interface ContextRequest {
  requestId: string;
  sessionId: string;
  paths: string[];
  reason: string;
  createdAt: unknown;
}

export interface ContextResponse {
  responseId: string;
  requestId: string;
  sessionId: string;
  files: ContextFile[];
  deniedPaths: string[];
  createdAt: unknown;
}
