/**
 * Runport TypeScript SDK Error hierarchy.
 *
 * Maps HTTP status codes and API v1 error codes into typed errors.
 */

export class RunportError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, statusCode: number, details?: Record<string, unknown>) {
    super(`[${code}] ${message}`);
    this.name = 'RunportError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details ?? {};
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class AuthenticationError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('unauthorized', message, 401, details);
    this.name = 'AuthenticationError';
  }
}

export class PermissionDeniedError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('forbidden', message, 403, details);
    this.name = 'PermissionDeniedError';
  }
}

export class ApprovalRequiredError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('approval_required', message, 428, details);
    this.name = 'ApprovalRequiredError';
  }
}

export class ApprovalInvalidError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('approval_invalid', message, 403, details);
    this.name = 'ApprovalInvalidError';
  }
}

export class PlanBlockedError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('plan_blocked', message, 409, details);
    this.name = 'PlanBlockedError';
  }
}

export class BudgetExceededError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('budget_exceeded', message, 402, details);
    this.name = 'BudgetExceededError';
  }
}

export class UnresolvedSpendError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('unresolved_spend', message, 409, details);
    this.name = 'UnresolvedSpendError';
  }
}

export class NotFoundError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('not_found', message, 404, details);
    this.name = 'NotFoundError';
  }
}

export class ConfidentialityViolationError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('confidentiality_violation', message, 400, details);
    this.name = 'ConfidentialityViolationError';
  }
}

export class InvalidTargetSpecError extends RunportError {
  constructor(message: string, details?: Record<string, unknown>) {
    super('invalid_target_spec', message, 400, details);
    this.name = 'InvalidTargetSpecError';
  }
}

export function createRunportError(statusCode: number, payload: unknown): RunportError {
  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    const err = (payload as { error: { code?: string; message?: string; details?: Record<string, unknown> } }).error;
    const code = err.code ?? 'unknown_error';
    const msg = err.message ?? 'An unknown error occurred.';
    const details = err.details ?? {};

    switch (code) {
      case 'unauthorized':
        return new AuthenticationError(msg, details);
      case 'forbidden':
        return new PermissionDeniedError(msg, details);
      case 'approval_required':
        return new ApprovalRequiredError(msg, details);
      case 'approval_invalid':
        return new ApprovalInvalidError(msg, details);
      case 'plan_blocked':
        return new PlanBlockedError(msg, details);
      case 'budget_exceeded':
        return new BudgetExceededError(msg, details);
      case 'unresolved_spend':
        return new UnresolvedSpendError(msg, details);
      case 'not_found':
        return new NotFoundError(msg, details);
      case 'confidentiality_violation':
        return new ConfidentialityViolationError(msg, details);
      case 'invalid_target_spec':
        return new InvalidTargetSpecError(msg, details);
      default:
        return new RunportError(code, msg, statusCode, details);
    }
  }

  return new RunportError('http_error', `HTTP ${statusCode}`, statusCode);
}
