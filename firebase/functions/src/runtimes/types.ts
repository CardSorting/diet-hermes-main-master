export interface RuntimeInput {
  sessionId: string;
  workspaceId: string;
  promptText: string;
  visibleFiles: any[];
  decisionContext?: any; // To pass execution results or other context
  history?: { role: string, content: string }[];
}

export interface RuntimeDecision {
  action: 'request_context' | 'propose_command' | 'propose_patch' | 'plan' | 'transcript' | 'error' | 'complete';
  paths?: string[];
  reason?: string;
  command?: string;
  cwd?: string;
  path?: string;
  diff?: string;
  steps?: string[];
  text?: string;
  error?: string;
  code?: string;
}

export interface RemoteRuntime {
  handlePrompt(input: RuntimeInput): Promise<RuntimeDecision | RuntimeDecision[]>;
  handleContextResponse(input: RuntimeInput): Promise<RuntimeDecision | RuntimeDecision[]>;
  handleExecutionResult(input: RuntimeInput): Promise<RuntimeDecision | RuntimeDecision[]>;
}
