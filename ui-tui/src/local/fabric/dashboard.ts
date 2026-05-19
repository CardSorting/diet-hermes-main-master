import { IntentGraph } from './policyVerifier.js'
import { ExecutionAttestation } from './replayVerifier.js'

export class OperatorDashboard {
  static drawHeader() {
    console.clear()
    console.log('\x1b[36m%s\x1b[0m', '================================================================================')
    console.log('\x1b[35m%s\x1b[0m', '      S O V E R E I G N   E X E C U T I O N   F A B R I C   D A S H B O A R D    ')
    console.log('\x1b[36m%s\x1b[0m', '================================================================================')
  }

  static drawTimeline(steps: { name: string; status: 'completed' | 'running' | 'pending' | 'failed' }[]) {
    console.log('\n\x1b[1m[ EXECUTION TIMELINE ]\x1b[0m')
    const line = steps.map(s => {
      let icon = '⚪'
      if (s.status === 'completed') icon = '\x1b[32m🟢\x1b[0m'
      if (s.status === 'running') icon = '\x1b[33m🟡\x1b[0m'
      if (s.status === 'failed') icon = '\x1b[31m🔴\x1b[0m'
      return `${icon} ${s.name}`
    }).join(' ──► ')
    console.log(`  ${line}`)
  }

  static drawIntentGraph(intent: IntentGraph, violations: string[]) {
    console.log('\n\x1b[1m[ INTENT GRAPH & COGNITIVE JUSTIFICATION ]\x1b[0m')
    console.log(`  \x1b[34mIntent ID:\x1b[0m ${intent.intentId} (\x1b[34mType:\x1b[0m ${intent.intentType})`)
    console.log(`  \x1b[34mJustification:\x1b[0m ${intent.cognitiveJustification.summaryJustification}`)
    console.log(`  \x1b[34mEvidence:\x1b[0m ${intent.cognitiveJustification.evidenceClaims.join(', ') || 'None'}`)
    console.log(`  \x1b[34mAssumptions:\x1b[0m ${intent.cognitiveJustification.dependencyAssumptions.join(', ') || 'None'}`)
    console.log(`  \x1b[34mConfidence:\x1b[0m ${intent.cognitiveJustification.confidenceEstimate * 100}%`)
    
    if (violations.length > 0) {
      console.log('  \x1b[41;37m RULES VIOLATIONS DETECTED! \x1b[0m')
      violations.forEach(v => console.log(`    \x1b[31m- ${v}\x1b[0m`))
    } else {
      console.log('  \x1b[42;30m PRE-FLIGHT COMPLIANCE: APPROVED \x1b[0m')
    }
  }

  static drawAttestationPanel(attestation: ExecutionAttestation | null, verified: boolean) {
    console.log('\n\x1b[1m[ CRYPTOGRAPHIC ATTESTATION AUDIT ]\x1b[0m')
    if (!attestation) {
      console.log('  \x1b[33mNo attestation emitted yet.\x1b[0m')
      return
    }
    console.log(`  \x1b[34mSignature:\x1b[0m ${attestation.signature.substring(0, 30)}...`)
    console.log(`  \x1b[34mWorker Key ID:\x1b[0m ${attestation.workerId}`)
    console.log(`  \x1b[34mInput commitment (Merkle Root):\x1b[0m ${attestation.inputHash}`)
    console.log(`  \x1b[34mOutput commitment:\x1b[0m ${attestation.outputHash}`)
    
    if (verified) {
      console.log('  \x1b[42;30m CRYPTOGRAPHIC AUDIT VERIFICATION: VALID \x1b[0m')
    } else {
      console.log('  \x1b[41;37m CRYPTOGRAPHIC AUDIT VERIFICATION: CORRUPTED SIGNATURE! \x1b[0m')
    }
  }

  static drawResourceMetrics(metrics: { universes: number; branchDepth: number; tokenSpend: number }) {
    console.log('\n\x1b[1m[ RESOURCE GOVERNANCE METRICS ]\x1b[0m')
    console.log(`  \x1b[34mSpeculative Universes Spawned:\x1b[0m ${metrics.universes} / 5`)
    console.log(`  \x1b[34mTimeline Branch Depth:\x1b[0m ${metrics.branchDepth} / 3`)
    console.log(`  \x1b[34mToken Spend:\x1b[0m $${metrics.tokenSpend.toFixed(4)}`)
  }

  static drawFooter() {
    console.log('\n\x1b[36m%s\x1b[0m', '================================================================================')
  }
}
