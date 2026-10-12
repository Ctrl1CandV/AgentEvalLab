import type { EventSink } from "./types.js";

/** Event persistence failure; propagate it instead of writing an incomplete success record. */
export class EventSinkError extends Error {
  constructor() {
    super("EVENT_SINK_FAILED");
    this.name = "EventSinkError";
  }
}

/**
 * Wrap an event sink so failures remain sticky:
 * after one emit fails, all later emits fail immediately,
 * and check() can rethrow the original failure at any time.
 * This protects against runners or SDKs that swallow listener exceptions.
 */
export function guardEventSink(sink: EventSink) {
  let failure: EventSinkError | undefined;

  const check = () => {
    if (failure) throw failure;
  };

  const emit: EventSink = async (type, counts, details) => {
    check();
    try {
      await sink(type, counts, details);
    } catch {
      failure = new EventSinkError();
      throw failure;
    }
  };

  return { emit, check };
}
