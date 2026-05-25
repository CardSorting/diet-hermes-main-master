import { Badge } from "@nous-research/ui/ui/components/badge";
import { HelpCircle } from "lucide-react";
import { useEffect, useState } from "react";
import {
  DIETCODE_PITCH,
  DIETCODE_TAGLINES,
  HOW_IT_WORKS,
} from "./copy";
import { DietCodeLogo } from "./DietCodeLogo";
import { SodaCanVisual } from "./SodaCanVisual";

export function DietCodeHeader() {
  const [showHelp, setShowHelp] = useState(false);
  const [taglineIdx, setTaglineIdx] = useState(
    () => new Date().getDate() % DIETCODE_TAGLINES.length
  );
  const tagline = DIETCODE_TAGLINES[taglineIdx]!;

  useEffect(() => {
    const id = window.setInterval(() => {
      setTaglineIdx((i) => (i + 1) % DIETCODE_TAGLINES.length);
    }, 8000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <header className="dc-header flex flex-col gap-4 border-b border-(--dc-cola)/25 pb-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4 min-w-0">
          <SodaCanVisual className="hidden sm:block w-14 h-auto shrink-0 dc-can-float" />
          <div className="min-w-0">
            <DietCodeLogo />
            <p className="text-[10px] uppercase tracking-[0.2em] text-(--dc-chrome) mt-2 font-semibold">
              Safe code changes · Extra fizz edition
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <Badge tone="success" className="dc-badge-cola text-[10px]">
            Carbonated · Alpha
          </Badge>
          <button
            type="button"
            onClick={() => setShowHelp((v) => !v)}
            className="dc-help-toggle flex items-center gap-1.5 text-[11px] text-midground/80 hover:text-midground normal-case tracking-normal"
            aria-expanded={showHelp}
          >
            <HelpCircle className="h-3.5 w-3.5" aria-hidden />
            {showHelp ? "Hide guide" : "How does this work?"}
          </button>
        </div>
      </div>

      <p
        key={taglineIdx}
        className="dc-tagline-strip dc-tagline-rotate m-0 text-sm font-medium italic"
      >
        {tagline}
      </p>
      <p className="text-sm text-midground/90 m-0 leading-relaxed max-w-3xl normal-case tracking-normal">
        {DIETCODE_PITCH}
      </p>

      {showHelp && (
        <section
          className="dc-how-it-works grid grid-cols-1 sm:grid-cols-3 gap-3 normal-case"
          aria-label="How DietCode works"
        >
          {HOW_IT_WORKS.map((item) => (
            <div key={item.step} className="dc-how-card flex gap-3 p-3 rounded-md">
              <span className="dc-how-step-num" aria-hidden>
                {item.step}
              </span>
              <div>
                <h2 className="text-xs font-bold text-midground m-0 uppercase tracking-wide">
                  {item.title}
                </h2>
                <p className="text-[11px] text-midground/75 m-0 mt-1 leading-relaxed">
                  {item.body}
                </p>
              </div>
            </div>
          ))}
        </section>
      )}
    </header>
  );
}
