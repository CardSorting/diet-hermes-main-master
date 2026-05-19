import { VerifiedExecutionPipeline } from './spine.js'
import { resolve } from 'node:path'

const workspaceRoot = resolve('.') // Target the active ui-tui directory
const pipeline = new VerifiedExecutionPipeline(workspaceRoot)

console.log('\n\x1b[32m[Fabric] Launching Bounded Operator Session Pipeline Demonstration...\x1b[0m\n')
pipeline.runPipelineFlow('add a simple test for this function', true, false).then(() => {
  console.log('\x1b[32m[Fabric] Operator Session Pipeline Demonstration Executed Successfully!\x1b[0m\n')
}).catch(console.error)
