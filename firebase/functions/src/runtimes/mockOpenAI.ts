import OpenAI from 'openai';
import { RemoteRuntime, RuntimeInput, RuntimeDecision } from './types.js';

export class OpenAIRemoteRuntime implements RemoteRuntime {
  private openai: OpenAI;

  constructor() {
    this.openai = new OpenAI(); // Requires OPENAI_API_KEY
  }

  async handlePrompt(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.decideNextStep(input);
  }

  async handleContextResponse(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.decideNextStep(input);
  }

  async handleExecutionResult(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.decideNextStep(input);
  }

  private async decideNextStep(input: RuntimeInput): Promise<RuntimeDecision[]> {
    const historyText = input.history ? input.history.map(h => `[${h.role.toUpperCase()}]: ${h.content}`).join('\n') : ''
    
    const systemPrompt = `You are the Sovereign Distributed Reasoning Engine.
The user has requested: "${input.promptText}"

Session Transcript:
${historyText}

Currently visible files:
${input.visibleFiles.map(f => `--- ${f.path} ---\n${f.content}\n`).join('\n') || 'None'}

You must respond in JSON with one of these structures:
1. To request files: { "action": "request_context", "paths": ["path/to/file1"], "reason": "why" }
2. To propose a shell command: { "action": "propose_command", "command": "cmd", "cwd": "dir", "reason": "why" }
3. To propose a file patch: { "action": "propose_patch", "path": "file.txt", "diff": "unified diff string", "reason": "why" }
`;

    try {
      const response = await this.openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [{ role: 'system', content: systemPrompt }],
        response_format: { type: 'json_object' }
      }, { timeout: 15000 });

      const decision = JSON.parse(response.choices[0].message.content || '{}');
      const decisions: RuntimeDecision[] = [];

      if (decision.action === 'request_context') {
        decisions.push({ action: 'request_context', paths: decision.paths, reason: decision.reason });
      } else {
        decisions.push({ action: 'plan', reason: decision.reason, steps: [decision.action === 'propose_command' ? 'Execute shell command' : 'Apply patch'] });
        if (decision.action === 'propose_command') {
          decisions.push({ action: 'propose_command', command: decision.command, cwd: decision.cwd || '.', reason: decision.reason });
        } else if (decision.action === 'propose_patch') {
          decisions.push({ action: 'propose_patch', path: decision.path, diff: decision.diff, reason: decision.reason });
        }
      }
      return decisions;
    } catch (e: any) {
      console.error('LLM error:', e);
      return [
        { action: 'transcript', text: 'Error reasoning about the request: ' + String(e) },
        { action: 'error', code: e.code || 'LLM_ERROR', error: e.message || String(e) }
      ];
    }
  }
}
