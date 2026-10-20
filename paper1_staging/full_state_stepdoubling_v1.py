"""Inactive, pure FULL-state trial decision and work-accounting kernel.

This module imports no model, solver, field or launcher. It cannot advance a
particle. The missing compiled-loop/evidence adapter is an explicit launch
blocker. A decision here never authenticates an original physical audit: its
future adapter must verify each supplied immutable witness before calling it.
No existing source, physical law, gate, binding or execution authority changes.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math


class Stop(RuntimeError):
    """Fail closed; this exception does not authorize another trial."""


def require(condition, message):
    if not condition:
        raise Stop(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def norm(values):
    return math.sqrt(math.fsum(float(x) ** 2 for x in values))


def difference(a, b):
    return norm([x - y for x, y in zip(a, b)])


@dataclass(frozen=True)
class Limits:
    """Supplemental *local* tolerances; none implies global accuracy.

    No default tolerances are selected: freeze them in a prospective design
    after analytical/engineering controls. Tests use artificial values only.
    """
    speed_m_s: float
    position_defect_m: float
    director_defect: float
    velocity_defect_over_U: float
    maximum_halvings: int
    minimum_h_s: float
    numerical_binding: str

    def validate(self):
        vals = [self.speed_m_s, self.position_defect_m, self.director_defect,
                self.velocity_defect_over_U, self.minimum_h_s]
        require(all(math.isfinite(x) and x > 0 for x in vals), "positive finite scales")
        require(type(self.maximum_halvings) is int and self.maximum_halvings >= 0,
                "finite halving ceiling")
        require(isinstance(self.numerical_binding, str) and len(self.numerical_binding) == 64
                and all(c in "0123456789abcdef" for c in self.numerical_binding),
                "frozen numerical binding")


@dataclass(frozen=True)
class Endpoint:
    time_s: float
    position_m: tuple
    director: tuple
    velocity_generalized: tuple
    full_checkpoint_sha256: str
    origin_full_checkpoint_sha256: str
    original_audit_receipt_sha256: str
    literal_raw_chain_sha256: str
    numerical_binding: str
    original_audits_passed: bool
    pending_original_trial: bool = False

    def validate(self, binding):
        require(len(self.position_m) == len(self.director) == 3
                and len(self.velocity_generalized) == 6, "FULL physical state dimensions")
        require(all(math.isfinite(x) for x in
                    (self.time_s, *self.position_m, *self.director,
                     *self.velocity_generalized)), "finite physical state")
        require(abs(norm(self.director) - 1) <= 1e-10, "original unit-director gate")
        for value in (self.full_checkpoint_sha256, self.origin_full_checkpoint_sha256,
                      self.original_audit_receipt_sha256, self.literal_raw_chain_sha256):
            require(len(value) == 64 and all(c in "0123456789abcdef" for c in value),
                    "immutable witness digest")
        require(self.numerical_binding == binding, "numerical source/input binding")
        require(self.original_audits_passed is True, "original physical/raw/evidence failure")
        require(self.pending_original_trial is False, "no unmatched original pending trial")


@dataclass(frozen=True)
class Decision:
    action: str
    position_defect_m: float
    director_defect: float
    velocity_defect_over_U: float
    scaled_defect: float
    next_h_s: float
    next_halving_depth: int
    committed_full_checkpoint_sha256: str | None
    discarded_full_checkpoint_sha256: tuple
    witness_sha256: str


def decide(limits, origin, h_s, original_selected_cap_s, halving_depth,
           coarse, first_half, second_half):
    """Judge one physically audited h versus two half-interval branches.

    Only the literal two-half-step FULL history can be committed. Histories
    are authenticated independently; their unequal row counts must never be
    normalized or compared as if they were equal. No Richardson state, sign
    flip, event matching, time shift or pose projection is performed.
    """
    limits.validate()
    require(type(halving_depth) is int and 0 <= halving_depth <= limits.maximum_halvings,
            "bounded trial depth")
    require(math.isfinite(h_s) and math.isfinite(original_selected_cap_s)
            and limits.minimum_h_s <= h_s <= original_selected_cap_s,
            "only tighten the original selected step")
    for endpoint in (origin, coarse, first_half, second_half):
        endpoint.validate(limits.numerical_binding)
    middle = origin.time_s + h_s / 2
    end = origin.time_s + h_s
    require(origin.time_s < middle < end, "nonzero representable half intervals")
    require(coarse.time_s == second_half.time_s == end and first_half.time_s == middle,
            "literal common physical endpoint; no time alignment")
    require(coarse.origin_full_checkpoint_sha256 == origin.full_checkpoint_sha256
            and first_half.origin_full_checkpoint_sha256 == origin.full_checkpoint_sha256
            and second_half.origin_full_checkpoint_sha256 == first_half.full_checkpoint_sha256,
            "identical FULL origin/history and contiguous half chain")
    dx = difference(coarse.position_m, second_half.position_m)
    dp = difference(coarse.director, second_half.director)
    dq = difference(coarse.velocity_generalized, second_half.velocity_generalized) / limits.speed_m_s
    score = max(dx / limits.position_defect_m, dp / limits.director_defect,
                dq / limits.velocity_defect_over_U)
    require(math.isfinite(score), "finite supplemental discrepancy")
    witness = digest(dict(limits=asdict(limits), origin=asdict(origin), h_s=h_s,
                          original_selected_cap_s=original_selected_cap_s,
                          halving_depth=halving_depth, coarse=asdict(coarse),
                          first_half=asdict(first_half), second_half=asdict(second_half)))
    if score <= 1:
        return Decision("commit_literal_halves", dx, dp, dq, score, h_s,
                        halving_depth, second_half.full_checkpoint_sha256,
                        (coarse.full_checkpoint_sha256,), witness)
    require(halving_depth < limits.maximum_halvings and h_s / 2 >= limits.minimum_h_s,
            "accuracy failed at bounded minimum; never force acceptance")
    return Decision("discard_all_and_halve", dx, dp, dq, score, h_s / 2,
                    halving_depth + 1, None,
                    (coarse.full_checkpoint_sha256, first_half.full_checkpoint_sha256,
                     second_half.full_checkpoint_sha256), witness)


@dataclass
class WorkLedger:
    """All screen work is diagnostic, including accepted candidate substeps.

    One native record may contain many complete trials. Trial substeps are
    NOT individual integration records, and the future compiled adapter must
    preserve that distinction. Unknown work is conservatively charged at its
    reservation, is never accepted, and prevents any successor reservation.
    """
    maximum_work_rows: int
    maximum_integration_records: int
    used_work_rows: int = 0
    used_integration_records: int = 0
    known_audited_rows: int = 0
    known_unaccepted_rows: int = 0
    unknown_reserved_rows: int = 0
    terminal_failure: str | None = None
    reservation: dict | None = None
    seen_record_ids: list = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self):
        numbers = (self.maximum_work_rows, self.maximum_integration_records,
                   self.used_work_rows, self.used_integration_records,
                   self.known_audited_rows, self.known_unaccepted_rows,
                   self.unknown_reserved_rows)
        require(all(type(v) is int and v >= 0 for v in numbers)
                and self.maximum_work_rows > 0 and self.maximum_integration_records > 0,
                "integer nonnegative ledger and positive caps")
        require(self.used_work_rows == self.known_audited_rows + self.known_unaccepted_rows
                + self.unknown_reserved_rows, "exact known/negative/unknown work partition")
        require(isinstance(self.seen_record_ids, list)
                and all(isinstance(v, str) and v for v in self.seen_record_ids)
                and len(set(self.seen_record_ids)) == len(self.seen_record_ids)
                and len(self.seen_record_ids) == self.used_integration_records,
                "literal unique record identities and actual record count")
        require(self.terminal_failure is None or isinstance(self.terminal_failure, str)
                and bool(self.terminal_failure), "persistent negative disposition")
        require((self.known_unaccepted_rows == self.unknown_reserved_rows == 0)
                or self.terminal_failure is not None, "unresolved work has terminal disposition")
        require(self.used_integration_records <= self.maximum_integration_records,
                "record accounting stays within admission cap")
        require(self.used_work_rows <= self.maximum_work_rows
                or self.terminal_failure is not None and self.known_unaccepted_rows > 0,
                "known overrun retained as negative actual work")
        if self.reservation is not None:
            require(set(self.reservation) == {"record_id", "maximum_rows"}
                    and self.seen_record_ids and self.reservation["record_id"] == self.seen_record_ids[-1]
                    and type(self.reservation["maximum_rows"]) is int
                    and 0 < self.reservation["maximum_rows"] <= 5000,
                    "literal pending reservation identity/cap")
            require(self.used_work_rows + self.reservation["maximum_rows"] <= self.maximum_work_rows
                    and self.terminal_failure is None, "pending work was admitted before dispatch")

    def reserve(self, record_id, maximum_rows):
        self.validate()
        require(self.reservation is None and self.unknown_reserved_rows == 0
                and self.known_unaccepted_rows == 0 and self.terminal_failure is None,
                "one record; unresolved or failed work stops even with zero rows")
        require(isinstance(record_id, str) and bool(record_id), "nonempty exact record identity")
        require(record_id not in self.seen_record_ids, "no duplicate integration record")
        require(type(maximum_rows) is int and 0 < maximum_rows <= 5000,
                "original 5000 work-row packet ceiling")
        require(self.used_work_rows + maximum_rows <= self.maximum_work_rows
                and self.used_integration_records + 1 <= self.maximum_integration_records,
                "strict shared/case/diagnostic admission envelope")
        self.reservation = dict(record_id=record_id, maximum_rows=maximum_rows)
        self.seen_record_ids.append(record_id)
        self.used_integration_records += 1

    def close(self, actual_rows, *, audited):
        self.validate()
        require(self.reservation is not None, "record reservation required")
        require(type(audited) is bool, "explicit independently verified audit result")
        require(type(actual_rows) is int and actual_rows >= 0,
                "nonnegative actual shadow/half/rejected/partial rows")
        if actual_rows > self.reservation["maximum_rows"]:
            # Preserve observed excess; never substitute a smaller reservation
            # for known actual work, even though the cap has been violated.
            self.used_work_rows += actual_rows
            self.known_unaccepted_rows += actual_rows
            self.terminal_failure = "known actual work exceeded the immutable reservation"
            self.reservation = None
            raise Stop(self.terminal_failure)
        self.used_work_rows += actual_rows
        if audited:
            self.known_audited_rows += actual_rows
        else:
            self.known_unaccepted_rows += actual_rows
            self.terminal_failure = "original audit/evidence failed, including zero-row failures"
        self.reservation = None

    def unresolved_exit(self):
        self.validate()
        require(self.reservation is not None, "unknown reservation required")
        self.unknown_reserved_rows += self.reservation["maximum_rows"]
        self.used_work_rows += self.reservation["maximum_rows"]
        self.terminal_failure = "unresolved exit conservatively charged at reservation"
        self.reservation = None

    def checkpoint(self):
        """Progress-only JSON; a future adapter must separately seal this."""
        self.validate()
        return json.loads(json.dumps(asdict(self), allow_nan=False))


@dataclass(frozen=True)
class TrialCheckpoint:
    """Pure controller cursor, including interruptions between branches.

    This embeds endpoint witness identities, not a substitute for literal
    original FULL checkpoints/raw history. The future adapter must supply and
    authenticate those external artifacts. Ledger reservations are checkpointed
    separately; restoring a cursor never releases or resolves a reservation.
    """
    limits: Limits
    origin: Endpoint
    h_s: float
    original_selected_cap_s: float
    halving_depth: int
    coarse: Endpoint | None = None
    first_half: Endpoint | None = None
    second_half: Endpoint | None = None

    def validate(self):
        self.limits.validate()
        self.origin.validate(self.limits.numerical_binding)
        require(math.isfinite(self.h_s) and math.isfinite(self.original_selected_cap_s)
                and self.limits.minimum_h_s <= self.h_s <= self.original_selected_cap_s,
                "checkpoint obeys original step cap")
        require(type(self.halving_depth) is int
                and 0 <= self.halving_depth <= self.limits.maximum_halvings,
                "checkpoint finite trial depth")
        require(self.origin.time_s < self.origin.time_s + self.h_s/2
                < self.origin.time_s + self.h_s, "checkpoint representable halves")
        require(not (self.first_half is not None and self.coarse is None)
                and not (self.second_half is not None and self.first_half is None),
                "ordered controller cursor")
        for role, item in (("coarse", self.coarse), ("first", self.first_half),
                           ("second", self.second_half)):
            if item is None:
                continue
            item.validate(self.limits.numerical_binding)
            wanted_time = self.origin.time_s + (self.h_s/2 if role == "first" else self.h_s)
            wanted_origin = (self.first_half.full_checkpoint_sha256 if role == "second"
                             else self.origin.full_checkpoint_sha256)
            require(item.time_s == wanted_time and item.origin_full_checkpoint_sha256 == wanted_origin,
                    "checkpoint exact branch clock/FULL ancestry")

    def append(self, endpoint):
        """Called only after independent external authentication of this branch."""
        self.validate()
        values = dict(limits=self.limits, origin=self.origin, h_s=self.h_s,
                      original_selected_cap_s=self.original_selected_cap_s,
                      halving_depth=self.halving_depth, coarse=self.coarse,
                      first_half=self.first_half, second_half=self.second_half)
        key = ("coarse" if self.coarse is None else "first_half"
               if self.first_half is None else "second_half" if self.second_half is None else None)
        require(key is not None, "no duplicate branch after complete trial")
        values[key] = endpoint
        result = TrialCheckpoint(**values)
        result.validate()
        return result

    def checkpoint(self):
        self.validate()
        payload = asdict(self)
        return dict(payload=payload, payload_sha256=digest(payload))

    @classmethod
    def restore(cls, envelope):
        require(digest(envelope["payload"]) == envelope["payload_sha256"],
                "literal controller checkpoint checksum")
        payload = dict(envelope["payload"])
        payload["limits"] = Limits(**payload["limits"])
        for key in ("origin", "coarse", "first_half", "second_half"):
            if payload[key] is not None:
                item = dict(payload[key])
                for name in ("position_m", "director", "velocity_generalized"):
                    item[name] = tuple(item[name])
                payload[key] = Endpoint(**item)
        result = cls(**payload)
        result.validate()
        return result

    def decision(self):
        self.validate()
        require(self.second_half is not None, "no output from partial controller trial")
        return decide(self.limits, self.origin, self.h_s, self.original_selected_cap_s,
                      self.halving_depth, self.coarse, self.first_half, self.second_half)


READINESS = dict(native_or_transport_imports=False, compiled_loop_adapter=False,
                 original_trial_auditor_adapter=False, controller_restart_qualified=False,
                 tolerance_policy_frozen=False, execution_authority=False,
                 numerical_launch_ready=False)
