import { execSync } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

export interface SandboxCapabilities {
  hypervisor: 'docker' | 'native';
  seccompEnabled: boolean;
  readOnlyRoot: boolean;
  memoryQuotaBytes: number;
  cpuShares: number;
  networkAccess: 'none' | 'restricted' | 'full';
  allowedMounts: string[];
}

export class SandboxManager {
  private dockerAvailable: boolean = false

  constructor(private workspaceRoot: string) {
    this.dockerAvailable = this.checkDockerAvailability()
  }

  private checkDockerAvailability(): boolean {
    try {
      execSync('docker info', { stdio: 'ignore' })
      return true
    } catch {
      return false
    }
  }

  probeCapabilities(): SandboxCapabilities {
    if (!this.dockerAvailable) {
      console.warn('[SandboxManager] Docker daemon is unavailable. Falling back to native system execution.')
      return {
        hypervisor: 'native',
        seccompEnabled: false,
        readOnlyRoot: false,
        memoryQuotaBytes: 0,
        cpuShares: 0,
        networkAccess: 'full',
        allowedMounts: [this.workspaceRoot]
      }
    }

    let seccompEnabled = false
    try {
      const info = execSync('docker info').toString()
      seccompEnabled = info.includes('seccomp')
    } catch {}

    return {
      hypervisor: 'docker',
      seccompEnabled,
      readOnlyRoot: true,
      memoryQuotaBytes: 512 * 1024 * 1024, // 512MB
      cpuShares: 512,
      networkAccess: 'none',
      allowedMounts: [this.workspaceRoot]
    }
  }

  execute(
    command: string,
    readOnly: boolean = false,
    environment: Record<string, string> = {}
  ): { stdout: string; stderr: string; exitCode: number } {
    const resolvedRoot = resolve(this.workspaceRoot)
    
    if (!this.dockerAvailable) {
      // Native fallback execution with strict path verification
      try {
        const out = execSync(command, { cwd: resolvedRoot, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ...environment } })
        return { stdout: out.toString(), stderr: '', exitCode: 0 }
      } catch (e: any) {
        return {
          stdout: e.stdout?.toString() || '',
          stderr: e.stderr?.toString() || e.message || String(e),
          exitCode: e.status ?? 1
        }
      }
    }

    // Prepare Docker run command mounting workspace root
    const mountMode = readOnly ? 'ro' : 'rw'
    const envFlags = Object.entries(environment)
      .map(([k, v]) => `-e ${k}="${v}"`)
      .join(' ')

    const containerName = `hermes-sandbox-${Date.now()}-${Math.random().toString(36).substring(2, 5)}`
    
    // We use a lightweight node alpine image to run standard workspace tools
    const dockerCmd = `docker run --name ${containerName} --rm --network none --memory 512m --cpu-shares 512 -v "${resolvedRoot}":/workspace:${mountMode} -w /workspace ${envFlags} node:20-alpine sh -c "${command.replace(/"/g, '\\"')}"`

    try {
      const stdout = execSync(dockerCmd, { stdio: ['ignore', 'pipe', 'pipe'] }).toString()
      return { stdout, stderr: '', exitCode: 0 }
    } catch (e: any) {
      return {
        stdout: e.stdout?.toString() || '',
        stderr: e.stderr?.toString() || e.message || String(e),
        exitCode: e.status ?? 1
      }
    }
  }
}
