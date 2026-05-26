import { ExternalLink, Play, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { DIETCODE_LIVE_AGENT_CTA, SESSION_STATUS_COPY, type SessionStatus } from "./copy";

interface DietCodeSessionBannerProps {
  status: SessionStatus;
  onStart: () => void;
  onReset: () => void;
  /** Dashboard preview — no simulated session progression. */
  demoMode?: boolean;
}

export function DietCodeSessionBanner({
  status,
  onStart,
  onReset,
  demoMode = false,
}: DietCodeSessionBannerProps) {
  const copy = SESSION_STATUS_COPY[status];
  const busy =
    status === "preflight" ||
    status === "applying" ||
    status === "testing";

  return (
    <section
      className={`dc-session-banner dc-session-banner--${copy.tone} flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-lg normal-case`}
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="flex items-start gap-3 min-w-0">
        {busy && (
          <Spinner className="text-[var(--dc-cola-bright)] shrink-0 mt-0.5" />
        )}
        <div>
          <p className="text-[10px] uppercase tracking-widest text-midground/50 m-0 mb-0.5">
            Session status
          </p>
          <p className="text-base font-bold text-midground m-0 tracking-normal">
            {copy.label}
          </p>
          <p className="text-xs text-midground/70 m-0 mt-1 leading-relaxed">
            {copy.hint}
          </p>
        </div>
      </div>

      <div className="flex gap-2 shrink-0 flex-wrap justify-end">
        {demoMode ? (
          <Button
            asChild
            className="dc-btn-primary h-10 px-5 text-xs font-bold normal-case"
          >
            <Link to={DIETCODE_LIVE_AGENT_CTA.chatPath}>
              <ExternalLink className="mr-2 h-4 w-4" aria-hidden />
              {DIETCODE_LIVE_AGENT_CTA.label}
            </Link>
          </Button>
        ) : (
          <>
            {status === "idle" && (
              <Button
                onClick={onStart}
                className="dc-btn-primary h-10 px-5 text-xs font-bold normal-case"
              >
                <Play className="mr-2 h-4 w-4" aria-hidden />
                Start session
              </Button>
            )}
            {status !== "idle" && (
              <Button
                onClick={onReset}
                className="h-9 px-4 text-xs font-semibold bg-black/50 border border-current/20 text-midground hover:bg-white/5 normal-case tracking-normal"
              >
                <RotateCw className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                Start over
              </Button>
            )}
          </>
        )}
      </div>
    </section>
  );
}
