import { readFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { execSync } from 'node:child_process'

export interface WorkspaceDomain {
  domainId: string;
  name: string;
  paths: string[];
  semanticLabels: string[];
  ownerHeuristics: {
    primaryAuthor: string;
    commitCount: number;
    dirtyState: boolean;
  };
}

export class SemanticClassifier {
  constructor(private workspaceRoot: string) {}

  classify(): WorkspaceDomain[] {
    const root = resolve(this.workspaceRoot)
    const domains: WorkspaceDomain[] = []

    // 1. Dependency and package metadata scanning
    const pkgPath = join(root, 'package.json')
    let dependencies: string[] = []
    if (existsSync(pkgPath)) {
      try {
        const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'))
        dependencies = Object.keys(pkg.dependencies || {}).concat(Object.keys(pkg.devDependencies || {}))
      } catch {}
    }

    // 2. Scan critical project directories and analyze Git ownership blame metrics
    const candidates = ['src', 'functions', 'ui-tui', 'services']
    for (const dir of candidates) {
      const fullPath = join(root, dir)
      if (existsSync(fullPath)) {
        let primaryAuthor = 'unknown'
        let commitCount = 0
        let dirtyState = false

        try {
          // Identify primary author of this directory via git blame commit frequencies
          const blameOut = execSync(`git shortlog -sn -- "${dir}"`, { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
          if (blameOut) {
            const firstLine = blameOut.split('\n')[0]
            const parts = firstLine.trim().split('\t')
            commitCount = parseInt(parts[0], 10)
            primaryAuthor = parts[1] || 'unknown'
          }

          const status = execSync(`git status --porcelain -- "${dir}"`, { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
          dirtyState = status.length > 0
        } catch {}

        // Compile semantic labels based on dependency connections and imports
        const semanticLabels: string[] = ['workspace_component', `${dir}_module`]
        if (dependencies.includes('firebase-admin') || dir.includes('functions')) {
          semanticLabels.push('backend_infrastructure', 'billing_pipeline')
        }
        if (dependencies.includes('react') || dir.includes('ui')) {
          semanticLabels.push('user_interface', 'presentation_layer')
        }

        domains.push({
          domainId: `sem-${dir}`,
          name: dir,
          paths: [dir],
          semanticLabels,
          ownerHeuristics: {
            primaryAuthor,
            commitCount,
            dirtyState
          }
        })
      }
    }

    // Default billing fallback category
    if (domains.length === 0) {
      domains.push({
        domainId: 'sem-fallback',
        name: 'default',
        paths: ['.'],
        semanticLabels: ['general_context'],
        ownerHeuristics: { primaryAuthor: 'developer', commitCount: 1, dirtyState: false }
      })
    }

    return domains;
  }
}
