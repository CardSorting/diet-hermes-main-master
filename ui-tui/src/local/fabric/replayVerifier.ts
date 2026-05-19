import { generateKeyPairSync, sign, verify } from 'node:crypto'
import { ExecutionJournal, ReplayDivergence } from '../worker.js'

export interface ExecutionAttestation {
  requestId: string;
  workerId: string;
  universeId: string;
  inputHash: string;
  outputHash: string;
  policyHash: string;
  replayHash?: string;
  signature: string;
  publicKey: string;
  timestamp: number;
}

export class ReplayVerifier {
  private publicKey: string
  private privateKey: string

  constructor() {
    const { publicKey, privateKey } = generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
    })
    this.publicKey = publicKey
    this.privateKey = privateKey
  }

  getPublicKey(): string {
    return this.publicKey
  }

  signAttestation(
    requestId: string,
    workerId: string,
    universeId: string,
    inputHash: string,
    outputHash: string,
    policyHash: string
  ): ExecutionAttestation {
    const payload = `${requestId}:${workerId}:${universeId}:${inputHash}:${outputHash}:${policyHash}`
    const signature = sign('sha256', Buffer.from(payload), {
      key: this.privateKey,
      padding: 1
    }).toString('base64')

    return {
      requestId,
      workerId,
      universeId,
      inputHash,
      outputHash,
      policyHash,
      signature,
      publicKey: this.publicKey,
      timestamp: Date.now()
    }
  }

  verifyAttestation(attestation: ExecutionAttestation): boolean {
    const payload = `${attestation.requestId}:${attestation.workerId}:${attestation.universeId}:${attestation.inputHash}:${attestation.outputHash}:${attestation.policyHash}`
    try {
      return verify('sha256', Buffer.from(payload), {
        key: attestation.publicKey,
        padding: 1
      }, Buffer.from(attestation.signature, 'base64'))
    } catch {
      return false
    }
  }
}
