/** Stylized wordmark — Diet Coke parody (Diet + Code, cola chrome). */

export function DietCodeLogo({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <span className="dc-logo-wordmark text-2xl leading-none" aria-label="DietCode">
        Diet<span className="text-[var(--dc-cola-bright)]">Code</span>
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-0.5">
      <h1 className="dc-logo-wordmark m-0" aria-label="DietCode">
        Diet<span style={{ WebkitTextStroke: "0px" }}>Code</span>
      </h1>
      <p className="dc-logo-sub m-0">Zero-calorie diffs · Maximum fizz</p>
    </div>
  );
}
