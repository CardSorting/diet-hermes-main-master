# Distributed Agent Runtime Architecture

## 1. Core Philosophy

The core problem with modern agentic coding tools is the tension between **compute ownership** and **workspace ownership**. 

* **Local-first agents** place extreme RAM pressure on developer hardware, introduce dependency fragility, and demand the user become a system administrator before they can work.
* **Fully hosted platforms** assume complete ownership of the execution environment, creating opaque runtime behaviors, lock-in, and fragile abstraction boundaries.

This architecture solves this by explicitly separating the two:
> **Compute ownership** moves to the cloud. **Workspace ownership** remains local.

The cloud runtime can reason, plan, index, orchestrate, and propose. The local workspace remains the definitive authority for files, git state, human approvals, and command execution.

## 2. Current Hermes-Agent Fit

The `hermes-agent` codebase is uniquely positioned to adopt this model due to its existing decoupled structure:

* **`ui-tui` (Ink React)**: Already acts as an interactive terminal interface decoupled from the orchestration loop.
* **`tui_gateway` & JSON-RPC Boundary**: Currently bridges the Node frontend and Python backend via `stdio`. This boundary is the natural seam to introduce remote networking.
* **`run_agent.py` & `AIAgent`**: The heavy orchestration, LLM interfacing, tool discovery, and context management loop.
* **`batch_runner.py` & Indexing**: Memory-intensive workloads that process trajectories, memories, and codebase structures.
* **Prompt Approval Components**: Existing UI components (`prompts.tsx`, `maskedPrompt.tsx`) form the foundation of the human-in-the-loop control surface.

In the distributed model, `ui-tui` and an execution-only subset of `tui_gateway` stay local. The entire `AIAgent`, memory engine, and orchestration loop migrate to the Remote Agent Runtime.

## 3. Local Thin Client Responsibilities

The local environment acts as a **human control surface**. It is a thin, reactive client rather than an orchestration engine.

Responsibilities include:
* **Transcript Rendering**: Displaying chat history, events, and context.
* **Status / Thinking Display**: Visualizing the remote agent's cognitive steps without executing them locally.
* **Diff Rendering**: Presenting proposed file changes clearly.
* **Approval Prompts**: Halting execution until explicit user consent is given for patches or commands.
* **Local Workspace Awareness**: Syncing current git state, cursor positions, and file paths to the remote runtime.
* **Execution Boundary**: Applying approved patches to the local filesystem and executing approved commands in the local shell.

## 4. Remote Agent Runtime Responsibilities

The remote runtime acts as the **orchestration and cognitive layer**. It bears the computational burden of the agent's intelligence.

Responsibilities include:
* **Planning & Orchestration**: Breaking down user intents into execution graphs.
* **Long-Context Reasoning**: Processing massive context windows and maintaining conversation history.
* **Indexing & Memory**: Storing, searching, and retrieving embeddings and structural data.
* **Provider Abstraction**: Interfacing with inference endpoints (OpenAI, Anthropic, OpenRouter) and managing API budgets.
* **Proposal Generation**: Bundling reasoning into actionable "Proposals" (patches, commands) for the client.
* **Streaming**: Emitting structured events back to the thin client over the network boundary.

## 5. Permission Boundary

The defining characteristic of this architecture is its explicit, non-bypassable permission model:

> **The cloud proposes.**
> **The local client reviews.**
> **The human approves.**
> **Execution occurs transparently.**

The remote runtime must **never** silently mutate the user’s machine. Every destructive or state-altering action—whether a file modification, a git commit, or a terminal command—must be serialized into a Proposal Event, transmitted to the client, and explicitly accepted by the human operator.

## 6. Transport Boundary

The current `tui_gateway` utilizes newline-delimited JSON-RPC over `stdio`. To enable cloud orchestration, this boundary is abstracted to support pluggable transports, specifically focusing on Firebase for the POC:

* **Local Mode**: Uses the existing `stdio` transport for offline or fully local inference. This remains the default.
* **Firebase Mode (Opt-in POC)**: Uses Firebase/Firestore as the primary transport, event, and proposal bus. The local client listens to realtime Firestore updates.
* **WebSocket/gRPC (Future)**: WebSocket and gRPC transports are considered future optimizations only, not the primary path for the current POC.

The local client remains the absolute execution authority, regardless of transport.

## 7. Payload Contracts

The JSON-RPC protocol will be extended to explicitly model the proposal/approval workflow. Key message types include:

* `stream.transcript`: Standard conversation appending.
* `stream.thinking`: Real-time status updates (e.g., "Indexing project...", "Reading utils.py").
* `proposal.plan`: A structured breakdown of intended steps.
* `proposal.patch`: A diff payload representing a file modification.
* `proposal.command`: A shell command intended for execution.
* `approval.request`: Sent by the cloud, blocking further action until resolved.
* `approval.response`: Sent by the client (granted/denied), unblocking the cloud runtime.
* `execution.result`: Sent by the client after applying a patch or running a command locally.
* `execution.error`: Sent by the client if a local operation fails.

## 8. Security Model

Security is paramount when connecting a developer's local machine to a remote orchestration engine.

* **Auth & Identity**: Connections established via ephemeral session tokens or OAuth, mapping to developer profiles.
* **Workspace UUIDs**: Every connected local project generates a unique UUID, preventing cross-contamination of context in the cloud.
* **Scoped Permissions**: The local client can define strict policy bounds (e.g., "Allow reads, prompt on writes, deny `rm -rf`").
* **Audit Logs**: All executed actions are recorded locally (`.hermes/logs/audit.log`) for complete forensic visibility.
* **No Blind Execution**: The remote runtime cannot force execution; it can only request it. The local client enforces the final check.

## 9. POC Plan

The implementation will be rolled out in isolated, testable phases focusing on Firebase and a mock runtime:

* **Phase 1: Architecture Definition** - Update the doc to clarify Firebase as the POC transport.
* **Phase 2: Shared Contracts** - Define Firebase runtime event types and payload contracts.
* **Phase 3: Transport Selector** - Introduce `HERMES_TRANSPORT=firebase` as an opt-in mode, keeping `stdio` as default.
* **Phase 4: Local Workspace Metadata** - Implement workspace metadata extraction.
* **Phase 5: Firebase Client Adapter** - Build the Firebase/Firestore subscription and event writing logic.
* **Phase 6: Render Firebase Events** - Map Firestore events into the existing TUI surfaces.
* **Phase 7: Patch Approval Flow** - Implement the local patch review, approval, and execution cycle.
* **Phase 8: Command Approval Flow** - Add remote command proposal and local policy execution.
* **Phase 9: Firebase Mock Runtime** - Implement a deterministic Firebase mock runtime (not the real `AIAgent`) to prove the control boundary.

A real `AIAgent` migration and WebSocket transports are explicitly non-goals for this initial POC.

> Run the agent in the cloud.
> Keep control in the local workspace.
