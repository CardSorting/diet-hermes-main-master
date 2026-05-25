import { useEffect, type ReactNode } from "react";
import { useTheme } from "@/themes";
import { CarbonationBackdrop } from "./CarbonationBackdrop";
import "./dietcode-brand.css";

const STORAGE_KEY = "hermes-dashboard-theme";

interface DietCodeShellProps {
  children: ReactNode;
  className?: string;
}

/**
 * Wraps DietCode routes with cola parody chrome + carbonation backdrop.
 * Applies the ``dietcode`` dashboard theme while mounted.
 */
export function DietCodeShell({ children, className = "" }: DietCodeShellProps) {
  const { setTheme } = useTheme();

  useEffect(() => {
    const prev =
      typeof window !== "undefined"
        ? window.localStorage.getItem(STORAGE_KEY) ?? "default"
        : "default";
    setTheme("dietcode");
    return () => {
      if (prev !== "dietcode") {
        setTheme(prev);
      }
    };
  }, [setTheme]);

  return (
    <div
      className={`dietcode-page relative flex flex-col gap-6 antialiased ${className}`}
      data-product="dietcode"
    >
      <CarbonationBackdrop density={52} bursts={10} condense={10} />
      <div className="relative z-[2] flex flex-col gap-6">{children}</div>
    </div>
  );
}
