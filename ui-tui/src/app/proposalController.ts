import { useState, useEffect } from 'react'
import type { GatewayClient } from '../gatewayClient.js'
import { executePatchLocally } from '../local/patchExecutor.js'
import { PatchProposal, CommandProposal } from '../firebase/contracts.js'
import { executeCommandLocally } from '../local/commandExecutor.js'
import { markProposalExecuted, isProposalExecuted } from '../local/state.js'

export function createProposalEventHandler(
  gw: GatewayClient, 
  activeProposal: PatchProposal | CommandProposal | null,
  setActiveProposal: (p: PatchProposal | CommandProposal | null) => void
) {
  return async (ev: any) => {
    if (ev.type === 'firebase.approval.request') {
      try {
        const proposalId = ev.payload.proposalId
        const root = process.cwd()

        if (isProposalExecuted(root, proposalId)) {
          console.warn(`Proposal ${proposalId} already executed locally. Ignoring.`)
          return
        }

        const proposal = await gw.request<PatchProposal | CommandProposal>('proposal.get', { id: proposalId })
        
        if (proposal.status === 'completed' || proposal.status === 'failed' || proposal.status === 'denied' || proposal.status === 'executing') {
          console.warn(`Proposal ${proposalId} is already in terminal state: ${proposal.status}`)
          return
        }

        setActiveProposal(proposal)

        const commandPreview = proposal.type === 'proposal.patch' 
          ? proposal.files.map(f => f.diff).join('\n')
          : proposal.command

        gw.emit('event', {
          type: 'approval.request',
          payload: {
            command: commandPreview,
            description: ev.payload.description
          }
        })
      } catch (e) {
        console.error('Failed to fetch proposal', e)
      }
    }

    if (ev.type === 'firebase.approval.decision') {
      const choice = ev.payload.choice
      const decision = choice === 'deny' ? 'denied' : 'approved'

      if (!activeProposal) return
      const proposal = activeProposal
      setActiveProposal(null)

      const root = process.cwd()

      if (isProposalExecuted(root, proposal.proposalId)) {
         console.warn(`Proposal ${proposal.proposalId} was already processed.`)
         return
      }

      try {
        await gw.request('firebase.proposal.updateStatus', { id: proposal.proposalId, status: decision })
        
        const approvalRes = await gw.request<{ success: boolean, approvalId: string }>('firebase.approval.write', { 
          id: proposal.proposalId, 
          decision 
        })

        const approvalId = approvalRes.approvalId

        if (decision === 'approved') {
          await gw.request('firebase.proposal.updateStatus', { id: proposal.proposalId, status: 'executing' })

          let result
          if (proposal.type === 'proposal.patch') {
            result = executePatchLocally(root, proposal.files, proposal.proposalId, approvalId)
            await gw.request('firebase.execution.write', {
              id: proposal.proposalId,
              result: {
                type: 'patch.apply',
                success: result.success,
                filesChanged: result.filesChanged,
                error: result.error
              }
            })
          } else if (proposal.type === 'proposal.command') {
            result = executeCommandLocally(root, proposal.command, proposal.cwd, proposal.proposalId, approvalId)
            await gw.request('firebase.execution.write', {
              id: proposal.proposalId,
              result: {
                type: 'command.run',
                success: result.success,
                stdout: result.stdout,
                stderr: result.stderr
              }
            })
          }

          if (result) {
            const finalStatus = result.success ? 'completed' : 'failed'
            await gw.request('firebase.proposal.updateStatus', { id: proposal.proposalId, status: finalStatus })
          }

          markProposalExecuted(root, proposal.proposalId)
        } else {
           markProposalExecuted(root, proposal.proposalId)
        }
      } catch (e) {
        console.error('Failed to handle decision', e)
      }
    }
  }
}

export function useProposalController(gw: GatewayClient) {
  const [activeProposal, setActiveProposal] = useState<PatchProposal | CommandProposal | null>(null)
  
  useEffect(() => {
    if (process.env.HERMES_TRANSPORT !== 'firebase') return
    const onEvent = createProposalEventHandler(gw, activeProposal, setActiveProposal)
    gw.on('event', onEvent)
    return () => {
      gw.off('event', onEvent)
    }
  }, [gw, activeProposal])

  return {}
}
