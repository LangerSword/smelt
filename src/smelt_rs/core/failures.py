"""Typed failures for the smelt pipeline.

Every failure mode the harness can produce has one class and one stable `kind`
string, so reports, tests, and CI can distinguish outcomes without string matching
on messages. Reviewed closely by the developer (acceptance semantics).
"""


class SmeltFailure(Exception):
    """Base class: a typed, reportable pipeline failure."""

    kind = "internal_error"

    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "details": self.details[:2000]}


class RefusedImpure(SmeltFailure):
    kind = "refused_impure"


class CaptureFailed(SmeltFailure):
    kind = "capture_failed"


class BuildError(SmeltFailure):
    kind = "build_error"

    def __init__(self, message: str, details: str = "", subkind: str = "unknown"):
        super().__init__(message, details)
        self.subkind = subkind


class SafetyViolation(SmeltFailure):
    kind = "safety_violation"


class VerifyMismatch(SmeltFailure):
    kind = "verify_mismatch"


class VerifyCrash(SmeltFailure):
    kind = "verify_crash"


class BenchInsufficient(SmeltFailure):
    kind = "bench_insufficient"


class BenchRegression(SmeltFailure):
    kind = "bench_regression"


class BudgetExhausted(SmeltFailure):
    kind = "budget_exhausted"


class ProviderError(SmeltFailure):
    kind = "provider_error"


class OracleTampered(SmeltFailure):
    kind = "oracle_tampered"


class TargetChanged(SmeltFailure):
    kind = "target_changed"


class ConfigError(SmeltFailure):
    kind = "config_error"
