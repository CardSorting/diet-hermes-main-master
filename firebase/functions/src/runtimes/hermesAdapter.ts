import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { RemoteRuntime, RuntimeInput, RuntimeDecision } from './types.js';

export class HermesRuntimeAdapter implements RemoteRuntime {
  
  async handlePrompt(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.runHermesBridge(input);
  }

  async handleContextResponse(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.runHermesBridge(input);
  }

  async handleExecutionResult(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return this.runHermesBridge(input);
  }

  private runHermesBridge(input: RuntimeInput): Promise<RuntimeDecision[]> {
    return new Promise((resolve, reject) => {
      // Assuming firebase/functions/ is cwd
      const scriptPath = join(__dirname, '../../scripts/hermes_bridge.py');
      const py = spawn('python3', [scriptPath]);
      
      let stdoutData = '';
      let stderrData = '';

      py.stdout.on('data', (chunk) => {
        stdoutData += chunk.toString();
      });

      py.stderr.on('data', (chunk) => {
        stderrData += chunk.toString();
      });

      py.on('close', (code) => {
        if (code !== 0) {
          console.error('Hermes bridge failed:', stderrData);
          resolve([
            { action: 'transcript', text: 'Hermes execution failed.' },
            { action: 'error', code: 'BRIDGE_ERROR', error: stderrData }
          ]);
          return;
        }

        try {
          const result = JSON.parse(stdoutData.trim());
          if (result.error) {
            resolve([
              { action: 'transcript', text: 'Hermes returned error: ' + result.error },
              { action: 'error', code: 'HERMES_ERROR', error: result.error }
            ]);
            return;
          }

          if (result.decisions && result.decisions.length > 0) {
            resolve(result.decisions);
          } else {
            resolve([{ action: 'transcript', text: 'Hermes finished without proposals.' }]);
          }
        } catch (e: any) {
          console.error('Failed to parse Hermes bridge output:', stdoutData);
          resolve([
            { action: 'transcript', text: 'Invalid JSON from Hermes.' },
            { action: 'error', code: 'PARSE_ERROR', error: String(e) }
          ]);
        }
      });

      // Pass input
      const payload = {
        prompt: input.promptText,
        files: input.visibleFiles,
        history: input.history || []
      };
      
      py.stdin.write(JSON.stringify(payload));
      py.stdin.end();
    });
  }
}
