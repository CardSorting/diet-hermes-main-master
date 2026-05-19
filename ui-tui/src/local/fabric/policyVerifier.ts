import { resolve } from 'node:path'
import { PolicyGraph, PolicyRule } from '../worker.js'
import { WorkspaceDomain } from './semanticClassifier.js'

export interface ToolPlanStep {
  tool: string
  args: any
  requiresApproval?: boolean
}

export interface CognitiveJustification {
  summaryJustification: string;
  evidenceClaims: string[];
  dependencyAssumptions: string[];
  confidenceEstimate: number; // 0.0 - 1.0
  provenanceReferences: string[];
}

export interface IntentGraph {
  intentId: string;
  intentType: 'patch' | 'test' | 'custom';
  plan: ToolPlanStep[];
  cognitiveJustification: CognitiveJustification;
}

export class PolicyVerifier {
  private compiledGraph: PolicyGraph

  constructor(
    policyText: string,
    private domains: WorkspaceDomain[]
  ) {
    this.compiledGraph = this.compilePolicy(policyText)
  }

  private compilePolicy(policyText: string): PolicyGraph {
    const rules: PolicyRule[] = []
    const constraints: PolicyGraph['constraints'] = {
      requiresApproval: true,
      forbiddenPaths: [],
      allowedPaths: []
    }

    const text = policyText.toLowerCase()
    
    // Compile "Block billing infrastructure modification"
    if (text.includes('billing') || text.includes('ledger')) {
      // Find semantic billing directories from domains
      const billingDomains = this.domains.filter(d => 
        d.semanticLabels.includes('billing_pipeline') || d.name.includes('functions')
      )
      
      const paths = billingDomains.flatMap(d => d.paths)
      constraints.forbiddenPaths = paths
      
      rules.push({
        ruleId: 'sem-billing-rule-1',
        effect: 'deny',
        actionPattern: 'write_file',
        condition: 'args.path.includes("functions") || args.path.includes("billing")'
      })
    }

    return {
      policyId: `policy-${Date.now()}`,
      rules,
      scopes: {},
      constraints
    };
  }

  verifyIntent(
    intent: IntentGraph,
    repoRoot: string
  ): { safe: boolean; violations: string[] } {
    const violations: string[] = []

    // 1. Verify structured cognitive justifications
    const justification = intent.cognitiveJustification
    if (justification.confidenceEstimate < 0.6) {
      violations.push(`Security violation: Cognition confidence estimate is too low (${justification.confidenceEstimate})`)
    }
    if (justification.evidenceClaims.length === 0) {
      violations.push('Security violation: No evidence claims found backing this intent.')
    }

    // 2. Verify planned steps against policy graph
    for (const step of intent.plan) {
      // Check path constraints
      if (step.args && step.args.path) {
        const resolvedPath = resolve(repoRoot, step.args.path)
        
        // Escape check
        if (!resolvedPath.startsWith(resolve(repoRoot))) {
          violations.push(`Security violation: Path escape detected on '${step.args.path}'`)
          continue
        }

        // Check forbidden domain paths
        const forbidden = this.compiledGraph.constraints.forbiddenPaths || []
        for (const fp of forbidden) {
          const resolvedForbidden = resolve(repoRoot, fp)
          if (resolvedPath.startsWith(resolvedForbidden)) {
            violations.push(`Policy violation: Tool '${step.tool}' modifies forbidden semantic billing domain path '${step.args.path}'`)
          }
        }
      }

      // Check rule effects
      for (const rule of this.compiledGraph.rules) {
        if (rule.effect === 'deny' && rule.actionPattern === step.tool) {
          if (rule.condition && step.args && step.args.path && step.args.path.includes('functions')) {
            violations.push(`Policy violation: Rule ${rule.ruleId} prohibits '${step.tool}' on billing paths.`)
          }
        }
      }
    }

    return {
      safe: violations.length === 0,
      violations
    }
  }
}
