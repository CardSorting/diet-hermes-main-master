import { useEffect } from 'react'
import type { GatewayClient } from '../gatewayClient.js'
import { readContextFile } from '../local/contextBuilder.js'

export function createContextEventHandler(gw: GatewayClient) {
  return async (ev: any) => {
    if (ev.type === 'firebase.context.request') {
      try {
        const root = process.cwd()
        const payload = ev.payload 
        
        const files = []
        const deniedPaths = []

        for (const p of payload.paths) {
          const file = readContextFile(root, p)
          if (file) {
            files.push(file)
          } else {
            deniedPaths.push(p)
          }
        }

        await gw.request('firebase.context.respond', {
          requestId: payload.requestId,
          files,
          deniedPaths
        })
      } catch (e) {
        console.error('Failed to handle context.request', e)
      }
    }
  }
}

export function useContextController(gw: GatewayClient) {
  useEffect(() => {
    if (process.env.HERMES_TRANSPORT !== 'firebase') return
    const onEvent = createContextEventHandler(gw)
    gw.on('event', onEvent)
    return () => {
      gw.off('event', onEvent)
    }
  }, [gw])
}
