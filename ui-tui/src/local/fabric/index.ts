import { SandboxManager } from './sandboxManager.js'
import { SemanticClassifier } from './semanticClassifier.js'
import { PolicyVerifier, IntentGraph } from './policyVerifier.js'
import { ReplayVerifier } from './replayVerifier.js'
import { OperatorDashboard } from './dashboard.js'
import { join } from 'node:path'

export async function runDemonstration(workspaceRoot: string) {
  console.log(`[Fabric] Initializing Bounded Operator Session Pipeline for root: ${workspaceRoot}`)

  // 1. Compile semantic workspace domains
  const classifier = new SemanticClassifier(workspaceRoot)
  const domains = classifier.classify()
  console.log(`[Classifier] Compiled ${domains.length} semantic domains from repository.`)

  // 2. Instantiate sandbox and policy engines
  const sandbox = new SandboxManager(workspaceRoot)
  const verifier = new PolicyVerifier('Block billing modifications without review', domains)
  const replay = new ReplayVerifier()

  // Define mock timeline progression tracking state
  const timeline: { name: string; status: 'completed' | 'running' | 'pending' | 'failed' }[] = [
    { name: 'Semantic Domain Map', status: 'completed' },
    { name: 'Pre-flight Policy Verification', status: 'pending' },
    { name: 'Docker Speculative Replay', status: 'pending' },
    { name: 'Sandboxed Mutator Execution', status: 'pending' },
    { name: 'Cryptographic Attestation', status: 'pending' }
  ]

  // =========================================================================
  // DEMO 1: HAPPY PATH RUNTIME RUN
  // =========================================================================
  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  
  // Define cognitive justifications to satisfy constraints
  const happyIntent: IntentGraph = {
    intentId: 'intent-happy-1',
    intentType: 'test',
    plan: [
      { tool: 'list_files', args: {}, requiresApproval: false }
    ],
    cognitiveJustification: {
      summaryJustification: 'Query workspace file list to check test consistency.',
      evidenceClaims: ['vitest command configurations exist in package.json'],
      dependencyAssumptions: ['vitest dependency package is installed'],
      confidenceEstimate: 0.95,
      provenanceReferences: ['package.json']
    }
  }

  // Pre-flight policy validation
  timeline[1].status = 'running'
  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  
  const check = verifier.verifyIntent(happyIntent, workspaceRoot)
  
  await new Promise(r => setTimeout(r, 1000))
  timeline[1].status = check.safe ? 'completed' : 'failed'
  timeline[2].status = 'running'
  
  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  OperatorDashboard.drawIntentGraph(happyIntent, check.violations)

  // Docker sandbox speculative dry-run execution
  await new Promise(r => setTimeout(r, 1000))
  const execution = sandbox.execute('node -v', true) // read-only dry run
  
  timeline[2].status = execution.exitCode === 0 ? 'completed' : 'failed'
  timeline[3].status = 'running'

  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  OperatorDashboard.drawIntentGraph(happyIntent, check.violations)

  // Real sandboxed workspace execution
  await new Promise(r => setTimeout(r, 1000))
  const writeExec = sandbox.execute('node -e "console.log(\'sandbox execution completed successfully\')"', false)

  timeline[3].status = writeExec.exitCode === 0 ? 'completed' : 'failed'
  timeline[4].status = 'running'

  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  OperatorDashboard.drawIntentGraph(happyIntent, check.violations)

  // Emits Cryptographic RSA Attestation signature validation
  await new Promise(r => setTimeout(r, 1000))
  const attestation = replay.signAttestation(
    'req-1',
    'worker-happy-1',
    'univ-happy-1',
    'merkle-root-ok',
    'stdout-hash-ok',
    'policy-hash-ok'
  )
  const isVerified = replay.verifyAttestation(attestation)

  timeline[4].status = isVerified ? 'completed' : 'failed'

  OperatorDashboard.drawHeader()
  OperatorDashboard.drawTimeline(timeline)
  OperatorDashboard.drawIntentGraph(happyIntent, check.violations)
  OperatorDashboard.drawAttestationPanel(attestation, isVerified)
  OperatorDashboard.drawResourceMetrics({ universes: 1, branchDepth: 1, tokenSpend: 0.0042 })
  OperatorDashboard.drawFooter()

  // =========================================================================
  // DEMO 2: REAL POLICY GRAPH VIOLATION
  // =========================================================================
  console.log('\n\x1b[33m[DEMO 2: POLICY GRAPH VIOLATION FAILURE REALISM]\x1b[0m')
  const maliciousIntent: IntentGraph = {
    intentId: 'intent-evil-2',
    intentType: 'patch',
    plan: [
      { tool: 'write_file', args: { path: 'functions/src/billing.ts' }, requiresApproval: true }
    ],
    cognitiveJustification: {
      summaryJustification: 'Directly modify core production billing file.',
      evidenceClaims: [],
      dependencyAssumptions: [],
      confidenceEstimate: 0.45, // Violates low confidence limit
      provenanceReferences: []
    }
  }

  const badCheck = verifier.verifyIntent(maliciousIntent, workspaceRoot)
  console.log(`  Intent proposed: ${maliciousIntent.cognitiveJustification.summaryJustification}`)
  console.log(`  \x1b[31mStatus: POLICY BLOCKED! Safe: ${badCheck.safe}\x1b[0m`)
  badCheck.violations.forEach(v => console.log(`    \x1b[31m- ${v}\x1b[0m`))

  // =========================================================================
  // DEMO 3: ATTESTATION CORRUPTION SIGNATURE FAILURE
  // =========================================================================
  console.log('\n\x1b[33m[DEMO 3: CRYPTOGRAPHIC ATTESTATION SIGNATURE CORRUPTION DETECTED]\x1b[0m')
  const tamperedAttestation = {
    ...attestation,
    signature: 'TAMPERED_OR_CORRUPTED_SIGNATURE'
  }
  const isTamperedVerified = replay.verifyAttestation(tamperedAttestation)
  console.log('  Attestation verification of tampered payload:')
  console.log(`  \x1b[31mVerified: ${isTamperedVerified} (SIGNATURE CORRUPTED!)\x1b[0m`)

  console.log('\n\x1b[32m[Fabric] Vertically integrated happy-path and failure realism demonstration complete!\x1b[0m\n')
}
