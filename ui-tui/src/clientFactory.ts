import { GatewayClient } from './gatewayClient.js'
import { FirebaseRuntimeClient } from './firebase/client.js'

export function createRuntimeClient(): GatewayClient {
  if (process.env.HERMES_TRANSPORT === 'firebase') {
    return new FirebaseRuntimeClient() as unknown as GatewayClient
  }
  return new GatewayClient()
}
