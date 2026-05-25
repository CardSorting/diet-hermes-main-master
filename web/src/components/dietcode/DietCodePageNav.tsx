import { BarChart3, Home, List } from "lucide-react";
import { DIETCODE_TABS, type DietCodeTabId } from "./copy";

const ICONS = {
  home: Home,
  chart: BarChart3,
  list: List,
} as const;

interface DietCodePageNavProps {
  active: DietCodeTabId;
  onChange: (tab: DietCodeTabId) => void;
}

/**
 * Segmented primary navigation — familiar pattern (Settings / app tabs).
 */
export function DietCodePageNav({ active, onChange }: DietCodePageNavProps) {
  return (
    <nav
      className="dc-page-nav flex flex-col gap-2"
      aria-label="DietCode sections"
    >
      <div
        className="dc-segmented flex flex-wrap gap-1 p-1 rounded-lg border border-(--dc-cola)/20 bg-black/40"
        role="tablist"
      >
        {DIETCODE_TABS.map((tab) => {
          const Icon = ICONS[tab.icon];
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`dietcode-panel-${tab.id}`}
              id={`dietcode-tab-${tab.id}`}
              onClick={() => onChange(tab.id)}
              className={
                isActive
                  ? "dc-segment-active flex-1 min-w-[7rem] flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-md text-xs font-bold uppercase tracking-wide"
                  : "dc-segment-idle flex-1 min-w-[7rem] flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-md text-xs font-semibold uppercase tracking-wide text-midground/70 hover:text-midground hover:bg-white/5"
              }
            >
              <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.shortLabel}</span>
            </button>
          );
        })}
      </div>
      <p className="text-[11px] text-midground/65 m-0 normal-case tracking-normal px-1">
        {DIETCODE_TABS.find((t) => t.id === active)?.description}
      </p>
    </nav>
  );
}
