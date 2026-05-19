import { EventEmitter } from 'node:events'
import { initializeApp } from 'firebase/app'
import { 
  getFirestore, 
  collection, 
  doc, 
  setDoc, 
  getDoc,
  onSnapshot, 
  query, 
  orderBy, 
  serverTimestamp,
} from 'firebase/firestore'
import { getAuth, signInAnonymously } from 'firebase/auth'
import { randomUUID } from 'node:crypto'

import { FirebaseRuntimeEvent, FirebaseSessionDocument } from './contracts.js'
import { collectFirebaseWorkspaceMetadata } from '../local/workspace.js'
import { ExecutionWorker } from '../local/worker.js'

const firebaseConfig = {
  apiKey: process.env.FIREBASE_API_KEY,
  authDomain: process.env.FIREBASE_AUTH_DOMAIN,
  projectId: process.env.FIREBASE_PROJECT_ID || "hermes-poc",
  storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.FIREBASE_APP_ID,
}

export class FirebaseRuntimeClient extends EventEmitter {
  private db: any
  private sessionId: string
  private workspaceRoot: string
  private unsubscribeEvents: (() => void) | null = null
  private worker: any = null

  constructor() {
    super()
    this.workspaceRoot = process.cwd()
    this.sessionId = process.env.HERMES_SESSION_ID || randomUUID()
  }

  async start() {
    try {
      const app = initializeApp(firebaseConfig)
      this.db = getFirestore(app)
      const auth = getAuth(app)
      
      // Connect to Firestore emulator if configured
      const firestoreHost = process.env.FIRESTORE_EMULATOR_HOST
      if (firestoreHost) {
        const { connectFirestoreEmulator } = await import('firebase/firestore')
        const [host, portStr] = firestoreHost.split(':')
        connectFirestoreEmulator(this.db, host, parseInt(portStr || '8080', 10))
        this.pushLog(`[firebase] connected to Firestore emulator at ${firestoreHost}`)
      }

      // Connect to Auth emulator if configured
      const authHost = process.env.FIREBASE_AUTH_EMULATOR_HOST
      if (authHost) {
        const { connectAuthEmulator } = await import('firebase/auth')
        connectAuthEmulator(auth, `http://${authHost}`)
        this.pushLog(`[firebase] connected to Auth emulator at ${authHost}`)
      }

      const userCred = await signInAnonymously(auth)
      const uid = userCred.user.uid

      const meta = collectFirebaseWorkspaceMetadata(this.workspaceRoot)

      const sessionRef = doc(this.db, 'sessions', this.sessionId)
      
      const sessionDoc: FirebaseSessionDocument = {
        sessionId: this.sessionId,
        workspaceId: meta.workspaceId,
        uid,
        status: 'active',
        mode: 'firebase',
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
        client: {
          type: 'tui',
          version: 'dev',
          platform: process.platform
        },
        workspace: meta
      }

      await setDoc(sessionRef, sessionDoc, { merge: true })

      this.subscribeToEvents()

      this.worker = new ExecutionWorker(this.db, this.sessionId, this.workspaceRoot)
      this.worker.start()

      this.emit('gateway.ready')
      this.pushLog(`[firebase] connected to session ${this.sessionId}`)
      
    } catch (error) {
      this.pushLog(`[firebase] init error: ${error}`)
    }
  }

  private subscribeToEvents() {
    const eventsRef = collection(this.db, 'sessions', this.sessionId, 'events')
    const q = query(eventsRef, orderBy('createdAt', 'asc'))

    this.unsubscribeEvents = onSnapshot(q, (snapshot) => {
      snapshot.docChanges().forEach((change) => {
        if (change.type === 'added') {
          const data = change.doc.data() as FirebaseRuntimeEvent
          if (data.source !== 'local-client') {
            this.handleRemoteEvent(data)
          }
        }
      })
    })
  }

  private handleRemoteEvent(event: FirebaseRuntimeEvent) {
    switch (event.type) {
      case 'stream.transcript':
        this.emit('event', { type: 'message.delta', payload: event.payload })
        break
      case 'stream.thinking':
        this.emit('event', { type: 'tool.progress', payload: event.payload })
        break
      case 'approval.request':
        this.emit('event', { 
          type: 'firebase.approval.request', 
          payload: { 
            proposalId: event.payload.proposalId as string,
            description: event.payload.description as string
          } 
        })
        break
      case 'context.request':
        this.emit('event', { 
          type: 'firebase.context.request', 
          payload: event.payload 
        })
        break
    }
  }

  drain() {}

  async request<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === 'prompt.submit') {
      const eventId = randomUUID()
      
      const { getGitStatus, readContextFile } = require('../local/contextBuilder.js')
      const git = getGitStatus(this.workspaceRoot)
      
      // Determine if there are files mentioned or dropped in the prompt
      // For POC, we'll try to extract simple file paths or just use empty if none
      const visibleFiles: any[] = []
      // We could parse params.prompt here for paths, but for now we rely on explicit context.request
      
      const contextId = randomUUID()
      const contextRef = doc(this.db, 'sessions', this.sessionId, 'context', contextId)
      const contextSnapshot = {
        type: 'context.snapshot',
        contextId,
        sessionId: this.sessionId,
        prompt: params.prompt as string,
        git,
        visibleFiles,
        createdAt: serverTimestamp()
      }
      
      await setDoc(contextRef, contextSnapshot)

      const event: FirebaseRuntimeEvent = {
        eventId,
        sessionId: this.sessionId,
        workspaceId: collectFirebaseWorkspaceMetadata(this.workspaceRoot).workspaceId,
        type: 'user.prompt',
        source: 'local-client',
        createdAt: serverTimestamp(),
        payload: { text: params.prompt, contextId }
      }
      
      await setDoc(doc(this.db, 'sessions', this.sessionId, 'events', eventId), event)
      return { id: eventId } as T
    } 
    
    if (method === 'proposal.get') {
      const docRef = doc(this.db, 'sessions', this.sessionId, 'proposals', params.id as string)
      const snap = await getDoc(docRef)
      return snap.data() as T
    }

    if (method === 'firebase.proposal.updateStatus') {
      const docRef = doc(this.db, 'sessions', this.sessionId, 'proposals', params.id as string)
      await setDoc(docRef, { status: params.status, updatedAt: serverTimestamp() }, { merge: true })
      return { success: true } as T
    }

    if (method === 'firebase.context.respond') {
      const responseId = params.requestId as string + '-response'
      const docRef = doc(this.db, 'sessions', this.sessionId, 'context', responseId)
      await setDoc(docRef, {
        type: 'context.response',
        responseId,
        requestId: params.requestId,
        files: params.files,
        deniedPaths: params.deniedPaths,
        createdAt: serverTimestamp()
      })
      
      const eventId = randomUUID()
      await setDoc(doc(this.db, 'sessions', this.sessionId, 'events', eventId), {
        eventId,
        sessionId: this.sessionId,
        workspaceId: collectFirebaseWorkspaceMetadata(this.workspaceRoot).workspaceId,
        type: 'context.response',
        source: 'local-client',
        createdAt: serverTimestamp(),
        payload: { responseId }
      })
      
      return { success: true } as T
    }

    if (method === 'firebase.context.writeSnapshot') {
      const docRef = doc(this.db, 'sessions', this.sessionId, 'context', params.contextId as string)
      await setDoc(docRef, {
        type: 'context.snapshot',
        contextId: params.contextId,
        prompt: params.prompt,
        git: params.git,
        visibleFiles: params.visibleFiles,
        createdAt: serverTimestamp()
      })
      return { success: true } as T
    }

    if (method === 'approval.respond') {
      this.emit('event', { type: 'firebase.approval.decision', payload: { choice: params.choice } })
      return Promise.resolve({} as T)
    }

    if (method === 'firebase.execution.write') {
      const executionId = randomUUID()
      const record = {
        executionId,
        proposalId: params.id,
        ...params.result as object,
        createdAt: serverTimestamp()
      }
      await setDoc(doc(this.db, 'sessions', this.sessionId, 'executions', executionId), record)
      return { success: true } as T
    }
    
    if (method === 'firebase.approval.write') {
      const approvalId = randomUUID()
      const record = {
        approvalId,
        proposalId: params.id,
        decision: params.decision,
        approvedBy: 'local-human',
        createdAt: serverTimestamp()
      }
      await setDoc(doc(this.db, 'sessions', this.sessionId, 'approvals', approvalId), record)
      return { success: true, approvalId } as T
    }
    
    return Promise.resolve({} as T)
  }

  kill() {
    if (this.worker) {
      this.worker.stop()
    }
    if (this.unsubscribeEvents) {
      this.unsubscribeEvents()
    }
    this.emit('exit', 0)
  }

  getLogTail(limit = 20): string {
    return '[firebase] mode active'
  }

  private pushLog(line: string) {
    this.emit('event', { type: 'gateway.stderr', payload: { line } })
  }
}
