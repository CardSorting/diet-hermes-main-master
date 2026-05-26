import { useCallback, useEffect, useState } from "react";
import { api, type DietCodeBroccoliHealth, type DietCodeBroccoliSnapshot } from "@/lib/api";
import type { SessionStatus } from "@/components/dietcode";

const DEFAULT_POLL_MS = 15_000;

export interface UseDietCodeBroccoliResult {
  isDemo: boolean;
  isLoading: boolean;
  health: DietCodeBroccoliHealth | null;
  snapshot: DietCodeBroccoliSnapshot | null;
  error: string | null;
  sessionStatus: SessionStatus;
  refresh: () => Promise<void>;
  approveProposal: (proposalId: string) => Promise<void>;
  denyProposal: (proposalId: string) => Promise<void>;
}

function mapSessionStatus(snapshot: DietCodeBroccoliSnapshot | null): SessionStatus {
  if (!snapshot?.success) return "idle";
  if (snapshot.pending_proposal_id) return "proposed";
  const active = snapshot.sessions?.find((s) =>
    ["active", "running", "pending"].includes((s.status || "").toLowerCase()),
  );
  if (active) {
    const st = (active.status || "").toLowerCase();
    if (st.includes("test")) return "testing";
    return "applying";
  }
  const recent = snapshot.sessions?.[0];
  if (recent) {
    const st = (recent.status || "").toLowerCase();
    if (st === "completed" || st === "success") return "success";
    if (st === "reverted" || st === "rolled_back") return "reverted";
    if (st === "failed" || st === "violation") return "violation";
  }
  return "idle";
}

export function useDietCodeBroccoli(pollMs = DEFAULT_POLL_MS): UseDietCodeBroccoliResult {
  const [health, setHealth] = useState<DietCodeBroccoliHealth | null>(null);
  const [snapshot, setSnapshot] = useState<DietCodeBroccoliSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const h = await api.getDietCodeHealth();
      setHealth(h);
      if (h.live) {
        const snap = await api.getDietCodeSnapshot();
        setSnapshot(snap);
        if (!snap.success) {
          setError(snap.error || h.message || "BroccoliDB snapshot unavailable");
        } else {
          setError(null);
        }
      } else {
        setSnapshot(null);
        setError(h.message || null);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setHealth(null);
      setSnapshot(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (pollMs <= 0) return;
    const id = window.setInterval(() => {
      void refresh();
    }, pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refresh]);

  const approveProposal = useCallback(
    async (proposalId: string) => {
      await api.dietCodeProposalAction(proposalId, "approve");
      await refresh();
    },
    [refresh],
  );

  const denyProposal = useCallback(
    async (proposalId: string) => {
      await api.dietCodeProposalAction(proposalId, "deny");
      await refresh();
    },
    [refresh],
  );

  const isDemo = !health?.live;

  return {
    isDemo,
    isLoading,
    health,
    snapshot,
    error,
    sessionStatus: isDemo ? "proposed" : mapSessionStatus(snapshot),
    refresh,
    approveProposal,
    denyProposal,
  };
}
