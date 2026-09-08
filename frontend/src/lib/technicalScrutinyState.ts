/**
 * Represents the presentation/reveal state of the Technical Scrutiny experience.
 * Note: This state machine controls visual revelation of backend-provided final results,
 * it does not represent actual live backend execution unless connected to an event stream.
 */
export enum ScrutinyState {
  IDLE = 'IDLE',
  LEVEL_ACTIVE = 'LEVEL_ACTIVE',
  CHECK_PROCESSING = 'CHECK_PROCESSING', // revealing a check (transient presentation state)
  CHECK_COMPLETED = 'CHECK_COMPLETED',
  LEVEL_COMPLETED = 'LEVEL_COMPLETED',
  OFFICER_PAUSED = 'OFFICER_PAUSED', // waiting for officer observation
  OFFICER_PROCEEDING = 'OFFICER_PROCEEDING', // saving observation
  NEXT_LEVEL = 'NEXT_LEVEL',
  SCRUTINY_COMPLETE = 'SCRUTINY_COMPLETE',
}
