import { Check } from "lucide-react";
import { WORKFLOW_STEPS, type SessionStatus } from "./copy";

/** Maps session status to how many workflow steps are complete (1–6). */
function completedStepCount(status: SessionStatus): number {
  switch (status) {
    case "idle":
      return 0;
    case "preflight":
      return 1;
    case "proposed":
      return 3;
    case "applying":
      return 4;
    case "testing":
      return 5;
    case "success":
      return 6;
    case "violation":
    case "reverted":
      return 3;
    default:
      return 0;
  }
}

interface DietCodeWorkflowStepperProps {
  status: SessionStatus;
}

/**
 * Horizontal progress stepper — familiar checkout / onboarding pattern.
 */
export function DietCodeWorkflowStepper({ status }: DietCodeWorkflowStepperProps) {
  const done = completedStepCount(status);

  return (
    <ol
      className="dc-workflow-stepper flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between list-none m-0 p-0 normal-case"
      aria-label="Session progress"
    >
      {WORKFLOW_STEPS.map((step, idx) => {
        const stepIndex = idx + 1;
        const isComplete = done >= stepIndex;
        const isCurrent = done + 1 === stepIndex && status !== "idle";
        return (
          <li
            key={step.id}
            className={`dc-workflow-step flex sm:flex-col items-center sm:items-center gap-2 sm:gap-1 flex-1 min-w-0 ${isCurrent ? "dc-workflow-step--current" : ""}`}
          >
            <div className="flex sm:flex-col items-center gap-2 sm:gap-1 w-full sm:w-auto">
              <span
                className={
                  isComplete
                    ? "dc-workflow-dot dc-workflow-dot--done"
                    : isCurrent
                      ? "dc-workflow-dot dc-workflow-dot--current"
                      : "dc-workflow-dot"
                }
                aria-current={isCurrent ? "step" : undefined}
              >
                {isComplete ? (
                  <Check className="h-3 w-3" strokeWidth={3} aria-hidden />
                ) : (
                  step.id
                )}
              </span>
              <div className="sm:text-center min-w-0 flex-1 sm:flex-none">
                <span className="block text-[10px] font-bold uppercase tracking-wide text-midground/90">
                  {step.label}
                </span>
                <span className="block text-[9px] text-midground/55 truncate sm:whitespace-normal">
                  {step.plain}
                </span>
              </div>
            </div>
            {idx < WORKFLOW_STEPS.length - 1 && (
              <span
                className="hidden sm:block dc-workflow-connector flex-1 h-px min-w-[8px] mx-1 mt-3"
                aria-hidden
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
