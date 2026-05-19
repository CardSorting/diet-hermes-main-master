import * as functions from 'firebase-functions'
import * as admin from 'firebase-admin'
import { handleNewEvent, handleNewExecution } from './mockRuntime.js'
import { HostedHermesRuntime } from './runtimes/hostedRuntime.js'

admin.initializeApp()

const db = admin.firestore()
const hostedRuntime = new HostedHermesRuntime(db)

export const onNewEvent = functions.firestore
  .document('sessions/{sessionId}/events/{eventId}')
  .onCreate(async (snap, context) => {
    const event = snap.data()
    const sessionId = context.params.sessionId

    // Route to new HostedHermesRuntime if it's one of the new event types
    const newTypes = ['user.message', 'approval.granted', 'approval.denied', 'tool.completed', 'tool.failed']
    if (newTypes.includes(event.type)) {
      await hostedRuntime.runStep(sessionId)
      return
    }

    // Fall back to legacy mock runtime
    await handleNewEvent(snap, context)
  })

export const onNewExecution = functions.firestore
  .document('sessions/{sessionId}/executions/{executionId}')
  .onCreate(async (snap, context) => {
    await handleNewExecution(snap, context)
  })
