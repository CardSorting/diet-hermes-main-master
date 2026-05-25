import { useMemo, type CSSProperties } from "react";
import "./dietcode-brand.css";

interface BubbleSpec {
  id: number;
  left: string;
  size: number;
  duration: number;
  delay: number;
  drift: number;
  layer: "back" | "mid" | "front";
}

interface BurstSpec {
  id: number;
  left: string;
  top: string;
  delay: number;
}

function buildBubbles(count: number): BubbleSpec[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    left: `${5 + ((i * 37) % 90)}%`,
    size: 4 + ((i * 13) % 22),
    duration: 4 + ((i * 7) % 10),
    delay: (i * 0.42) % 8,
    drift: ((i % 7) - 3) * 14,
    layer: (["back", "mid", "front"] as const)[i % 3]!,
  }));
}

function buildBursts(count: number): BurstSpec[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    left: `${10 + ((i * 29) % 80)}%`,
    top: `${15 + ((i * 19) % 70)}%`,
    delay: (i * 2.3) % 9,
  }));
}

function buildCondenseLines(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    left: `${12 + ((i * 23) % 76)}%`,
    delay: `${(i * 1.7) % 6}s`,
  }));
}

/** Rising bubble field + burst pops — soda carbonation parody backdrop. */
export function CarbonationBackdrop({
  density = 48,
  bursts = 8,
  condense = 8,
}: {
  density?: number;
  bursts?: number;
  condense?: number;
}) {
  const bubbles = useMemo(() => buildBubbles(density), [density]);
  const burstSpecs = useMemo(() => buildBursts(bursts), [bursts]);
  const lines = useMemo(() => buildCondenseLines(condense), [condense]);

  return (
    <div className="dc-bubbles-layer" aria-hidden>
      <div className="dc-fizz-band" />
      <div className="dc-fizz-ripple" />
      {lines.map((line) => (
        <span
          key={`c-${line.id}`}
          className="dc-condense-line"
          style={{ left: line.left, animationDelay: line.delay }}
        />
      ))}
      {burstSpecs.map((b) => (
        <span
          key={`burst-${b.id}`}
          className="dc-fizz-burst"
          style={{
            left: b.left,
            top: b.top,
            animationDelay: `${b.delay}s`,
          }}
        />
      ))}
      {bubbles.map((b) => {
        const style = {
          left: b.left,
          width: `${b.size}px`,
          height: `${b.size}px`,
          "--dc-duration": `${b.duration}s`,
          "--dc-delay": `${b.delay}s`,
          "--dc-drift": `${b.drift}px`,
        } as CSSProperties;
        return (
          <span
            key={b.id}
            className={`dc-bubble dc-bubble--${b.layer}`}
            style={style}
          />
        );
      })}
    </div>
  );
}
