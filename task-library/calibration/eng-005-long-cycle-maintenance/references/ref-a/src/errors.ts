export type ErrorCode =
  | "INVALID_ARGUMENT" | "NOT_FOUND" | "DUPLICATE_ID" | "INVALID_STATUS_TRANSITION"
  | "SELF_DEPENDENCY" | "DEPENDENCY_CYCLE" | "DEPENDENCY_NOT_COMPLETE" | "STORE_INVALID" | "UNKNOWN_COMMAND";

export class AppError extends Error {
  readonly code: ErrorCode;

  constructor(code: ErrorCode, message: string) {
    super(message);
    this.code = code;
    this.name = "AppError";
  }
}

export function invalid(message: string): never {
  throw new AppError("INVALID_ARGUMENT", message);
}
