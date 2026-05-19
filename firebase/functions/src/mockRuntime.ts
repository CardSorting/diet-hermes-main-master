import * as admin from 'firebase-admin'
import { RemoteRuntime, RuntimeInput, RuntimeDecision } from './runtimes/types.js'
import { OpenAIRemoteRuntime } from './runtimes/mockOpenAI.js'
import { HermesRuntimeAdapter } from './runtimes/hermesAdapter.js'

const db = admin.firestore()

function getRuntime(): RemoteRuntime {
  const rt = process.env.REMOTE_RUNTIME || 'mock_openai'
  if (rt === 'hermes') {
    return new HermesRuntimeAdapter()
  }
  return new OpenAIRemoteRuntime()
}

export async function handleNewEvent(snap: admin.firestore.QueryDocumentSnapshot, context: any) {
  const event = snap.data()
  if (event.source !== 'local-client') return 
  
  const sessionId = context.params.sessionId
  if (!(await checkSafetyBounds(sessionId))) return

  const runtime = getRuntime()

  if (event.type === 'user.prompt') {
    await writeThinking(sessionId, event.workspaceId, 'Thinking about your request...')
    
    const contextId = event.payload.contextId
    let promptText = event.payload.text || ''

    let visibleFiles: any[] = []
    if (contextId) {
      const cSnap = await db.collection('sessions').doc(sessionId).collection('context').doc(contextId).get()
      if (cSnap.exists) {
        const packet = cSnap.data()
        promptText = packet?.prompt || promptText
        visibleFiles = packet?.visibleFiles || []
      }
    }

    const history = await fetchConversationHistory(sessionId)
    const input: RuntimeInput = { sessionId, workspaceId: event.workspaceId, promptText, visibleFiles, history }
    const decisions = await runtime.handlePrompt(input)
    await processDecisions(sessionId, event.workspaceId, decisions)
  }

  if (event.type === 'context.response') {
    await writeThinking(sessionId, event.workspaceId, 'Context received, reasoning...')
    
    const responseId = event.payload.responseId
    const cSnap = await db.collection('sessions').doc(sessionId).collection('context').doc(responseId).get()
    const ctxResp = cSnap.data() || {}

    const evSnap = await db.collection('sessions').doc(sessionId).collection('events')
      .where('type', '==', 'user.prompt')
      .orderBy('createdAt', 'desc').limit(1).get()
    
    const promptText = evSnap.docs[0]?.data().payload.text || ''

    const history = await fetchConversationHistory(sessionId)
    const input: RuntimeInput = { sessionId, workspaceId: event.workspaceId, promptText, visibleFiles: ctxResp.files || [], history }
    const decisions = await runtime.handleContextResponse(input)
    await processDecisions(sessionId, event.workspaceId, decisions)
  }
}

async function checkSafetyBounds(sessionId: string): Promise<boolean> {
  const evSnap = await db.collection('sessions').doc(sessionId).collection('events').get()
  
  let steps = 0
  let proposals = 0
  let filesRequested = 0

  for (const doc of evSnap.docs) {
    const ev = doc.data()
    if (ev.type === 'session.complete' || ev.type === 'session.failed' || ev.type === 'session.cancel.request' || ev.type === 'session.max_steps_exceeded') {
      return false // Terminal state reached, block execution
    }
    if (ev.type === 'stream.thinking') steps++
    if (ev.type === 'approval.request') proposals++
    if (ev.type === 'context.request') filesRequested += (ev.payload?.paths?.length || 0)
  }

  if (steps >= 10 || proposals >= 5 || filesRequested >= 10) {
    await db.collection('sessions').doc(sessionId).collection('events').add({
      eventId: 'err-' + Date.now(),
      sessionId,
      workspaceId: 'any',
      type: 'session.max_steps_exceeded',
      source: 'remote-runtime',
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      payload: { reason: `Safety limits exceeded. Steps: ${steps}, Proposals: ${proposals}, Files: ${filesRequested}` }
    })
    return false
  }

  return true
}

async function fetchConversationHistory(sessionId: string) {
  const evSnap = await db.collection('sessions').doc(sessionId).collection('events')
    .orderBy('createdAt', 'asc').get()
  
  const history: any[] = []
  
  for (const doc of evSnap.docs) {
    const ev = doc.data()
    if (ev.type === 'user.prompt') {
      history.push({ role: 'user', content: ev.payload.text })
    } else if (ev.type === 'proposal.plan') {
      history.push({ role: 'assistant', content: `[Created Plan]` })
    } else if (ev.type === 'approval.request') {
      history.push({ role: 'assistant', content: `[Proposed Action]: ${ev.payload.description}` })
    } else if (ev.type === 'context.request') {
      history.push({ role: 'assistant', content: `[Requested Context]: ${ev.payload.paths?.join(', ')}` })
    } else if (ev.type === 'context.response') {
      history.push({ role: 'user', content: `[Context Provided]` })
    } else if (ev.type === 'stream.transcript') {
      history.push({ role: 'assistant', content: ev.payload.text })
    } else if (ev.type === 'session.complete') {
      history.push({ role: 'user', content: `[Execution Complete]` })
    } else if (ev.type === 'execution.result') {
      const ex = ev.payload
      history.push({ role: 'user', content: `[Execution Result]: Success: ${ex.success}\nStdout: ${ex.stdout || ''}\nStderr: ${ex.stderr || ''}` })
    }
  }
  return history
}


export async function handleNewExecution(snap: admin.firestore.QueryDocumentSnapshot, context: any) {
  const execution = snap.data()
  const sessionId = context.params.sessionId
  
  const eventRef = db.collection('sessions').doc(sessionId).collection('events').doc('ex-' + snap.id)
  try {
    await eventRef.create({
      eventId: 'ex-' + snap.id,
      sessionId,
      workspaceId: 'any',
      type: 'execution.result',
      source: 'local-client',
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      payload: execution
    })
  } catch (e) {
    // Already created, duplicate trigger
    return
  }

  if (!(await checkSafetyBounds(sessionId))) return

  await writeThinking(sessionId, 'any', 'Execution result received, continuing reasoning...')

  const history = await fetchConversationHistory(sessionId)
  const runtime = getRuntime()
  
  const input: RuntimeInput = { 
    sessionId, 
    workspaceId: 'any', 
    promptText: '', 
    visibleFiles: [], // Context will be re-requested by the agent if needed
    history
  }
  
  const decisions = await runtime.handleExecutionResult(input)
  await processDecisions(sessionId, 'any', decisions)
}

async function processDecisions(sessionId: string, workspaceId: string, decisions: RuntimeDecision | RuntimeDecision[]) {
  const decisionArray = Array.isArray(decisions) ? decisions : [decisions]
  for (const decision of decisionArray) {
    if (decision.action === 'request_context') {
      const requestId = 'req-' + Date.now()
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'cr-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'context.request',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: { requestId, paths: decision.paths, reason: decision.reason }
      })
    } else if (decision.action === 'plan') {
      const planId = 'plan-' + Date.now()
      await db.collection('sessions').doc(sessionId).collection('proposals').doc(planId).set({
        proposalId: planId,
        type: 'proposal.plan',
        status: 'pending_approval',
        summary: decision.reason || 'Reasoning',
        steps: decision.steps || [],
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      })
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'plan-ev-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'proposal.plan',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: { proposalId: planId }
      })
    } else if (decision.action === 'propose_command') {
      const proposalId = 'cmd-' + Date.now()
      await db.collection('sessions').doc(sessionId).collection('proposals').doc(proposalId).set({
        proposalId,
        type: 'proposal.command',
        status: 'pending_approval',
        riskLevel: 'medium',
        command: decision.command,
        cwd: decision.cwd || '.',
        reason: decision.reason || 'Executing command',
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      })
      
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'ar-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'approval.request',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: { proposalId, description: decision.reason }
      })
    } else if (decision.action === 'propose_patch') {
      const proposalId = 'patch-' + Date.now()
      await db.collection('sessions').doc(sessionId).collection('proposals').doc(proposalId).set({
        proposalId,
        type: 'proposal.patch',
        status: 'pending_approval',
        riskLevel: 'medium',
        summary: decision.reason || 'Applying patch',
        reason: decision.reason || 'Applying patch',
        files: [{ path: decision.path, diff: decision.diff }],
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      })
      
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'ar-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'approval.request',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: { proposalId, description: decision.reason }
      })
    } else if (decision.action === 'transcript') {
      await writeTranscript(sessionId, workspaceId, decision.text || '')
    } else if (decision.action === 'error') {
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'err-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'session.error',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: { code: decision.code || 'ERROR', message: decision.error }
      })
    } else if (decision.action === 'complete') {
      await db.collection('sessions').doc(sessionId).collection('events').add({
        eventId: 'sc-' + Date.now(),
        sessionId,
        workspaceId,
        type: 'session.complete',
        source: 'remote-runtime',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        payload: {}
      })
    }
  }
}

async function writeThinking(sessionId: string, workspaceId: string, message: string) {
  await db.collection('sessions').doc(sessionId).collection('events').add({
    eventId: 'st-' + Date.now(),
    sessionId,
    workspaceId,
    type: 'stream.thinking',
    source: 'remote-runtime',
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    payload: { message }
  })
}

async function writeTranscript(sessionId: string, workspaceId: string, text: string) {
  await db.collection('sessions').doc(sessionId).collection('events').add({
    eventId: 'tr-' + Date.now(),
    sessionId,
    workspaceId,
    type: 'stream.transcript',
    source: 'remote-runtime',
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    payload: { role: 'assistant', text }
  })
}

