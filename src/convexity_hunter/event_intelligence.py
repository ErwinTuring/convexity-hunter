"""Provider-neutral Event Intelligence submission and acceptance boundary."""

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Set, Tuple, Type

from .market_data import UnderlyingKey


__all__ = (
    "EventSourceReference",
    "EventStatementKind",
    "EventStatement",
    "MethodologizedDateRange",
    "DistributionChangeMode",
    "EventUnderlyingHypothesis",
    "EventIntelligenceSubmission",
    "EventIntelligenceAcceptanceStatus",
    "EventIntelligenceIssueCode",
    "EventIntelligenceAcceptanceIssue",
    "EventIntelligenceAcceptanceResult",
    "assess_event_intelligence_submission",
)


_ASSESSMENT_VERSION = "event-intelligence-acceptance-v0.1"


def _normalize_required_string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _normalize_optional_string(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    return _normalize_required_string(name, value)


def _normalize_utc_datetime(
    name: str, value: object
) -> datetime.datetime:
    if not isinstance(value, datetime.datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(datetime.timezone.utc)


def _normalize_optional_utc_datetime(
    name: str, value: object
) -> Optional[datetime.datetime]:
    if value is None:
        return None
    return _normalize_utc_datetime(name, value)


def _validate_optional_date_only(name: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, datetime.datetime) or not isinstance(
        value, datetime.date
    ):
        raise TypeError(f"{name} must be a date without a time component")


def _normalize_id_tuple(name: str, values: object) -> Tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    normalized = tuple(
        _normalize_required_string(f"{name} item", item) for item in values
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(normalized))


def _normalize_text_tuple(name: str, values: object) -> Tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    normalized = tuple(
        _normalize_required_string(f"{name} item", item) for item in values
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(normalized))


def _normalize_record_tuple(
    name: str, values: object, record_type: Type[object], id_name: str
) -> Tuple[object, ...]:
    if type(values) not in {tuple, list}:
        raise TypeError(f"{name} must be a tuple or list")
    normalized = tuple(values)
    if not all(type(item) is record_type for item in normalized):
        raise TypeError(
            f"every {name} item must have exact type {record_type.__name__}"
        )
    try:
        identifiers = tuple(getattr(item, id_name) for item in normalized)
    except AttributeError as error:
        raise ValueError(f"{name} contains a malformed record") from error
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name} must not contain duplicate {id_name} values")
    return tuple(sorted(normalized, key=lambda item: getattr(item, id_name)))


def _require_intrinsic_record(
    name: str,
    value: object,
    record_type: Type[object],
    field_names: Tuple[str, ...],
) -> None:
    """Reconstruct one exact frozen record to reject constructor bypasses."""

    if type(value) is not record_type:
        raise TypeError(f"{name} must have exact type {record_type.__name__}")
    try:
        rebuilt = record_type(*(getattr(value, field) for field in field_names))
    except AttributeError as error:
        raise ValueError(f"{name} is malformed") from error
    if rebuilt != value:
        raise ValueError(f"{name} is not intrinsically valid")


def _require_underlying_key(value: object) -> None:
    _require_intrinsic_record(
        "underlying_key",
        value,
        UnderlyingKey,
        ("symbol", "listing_mic", "security_type", "currency"),
    )


def _require_date_range(name: str, value: object) -> None:
    _require_intrinsic_record(
        name,
        value,
        MethodologizedDateRange,
        ("start_date", "end_date", "methodology"),
    )


@dataclass(frozen=True)
class EventSourceReference:
    """One structured source cited by an Event Intelligence submission."""

    source_id: str
    locator: Optional[str]
    title: Optional[str] = None
    published_at: Optional[datetime.datetime] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_id", _normalize_required_string("source_id", self.source_id)
        )
        object.__setattr__(
            self, "locator", _normalize_optional_string("locator", self.locator)
        )
        object.__setattr__(
            self, "title", _normalize_optional_string("title", self.title)
        )
        object.__setattr__(
            self,
            "published_at",
            _normalize_optional_utc_datetime("published_at", self.published_at),
        )


class EventStatementKind(str, Enum):
    """Whether a statement reports a source fact or an interpretation."""

    OBSERVED_FACT = "observed_fact"
    INTERPRETATION = "interpretation"


@dataclass(frozen=True)
class EventStatement:
    """One source-bound fact or explicit interpretation."""

    statement_id: str
    kind: EventStatementKind
    text: Optional[str]
    source_ids: Tuple[str, ...] = ()
    dependency_statement_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        statement_id = _normalize_required_string(
            "statement_id", self.statement_id
        )
        if not isinstance(self.kind, EventStatementKind):
            raise TypeError("kind must be an EventStatementKind")
        text = _normalize_optional_string("text", self.text)
        source_ids = _normalize_id_tuple("source_ids", self.source_ids)
        dependency_ids = _normalize_id_tuple(
            "dependency_statement_ids", self.dependency_statement_ids
        )
        if statement_id in dependency_ids:
            raise ValueError("a statement must not depend on itself")
        if (
            self.kind is EventStatementKind.OBSERVED_FACT
            and dependency_ids
        ):
            raise ValueError("observed facts must not declare statement dependencies")
        object.__setattr__(self, "statement_id", statement_id)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "dependency_statement_ids", dependency_ids)


@dataclass(frozen=True)
class MethodologizedDateRange:
    """An inclusive date range with explicit derivation methodology."""

    start_date: Optional[datetime.date]
    end_date: Optional[datetime.date]
    methodology: Optional[str]

    def __post_init__(self) -> None:
        _validate_optional_date_only("start_date", self.start_date)
        _validate_optional_date_only("end_date", self.end_date)
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must not be after end_date")
        object.__setattr__(
            self,
            "methodology",
            _normalize_optional_string("methodology", self.methodology),
        )


class DistributionChangeMode(str, Enum):
    """Closed MVP hypothesis modes for a future return distribution."""

    EXTREME_TAIL_UP = "extreme_tail_up"
    EXTREME_TAIL_DOWN = "extreme_tail_down"
    EVENT_DIRECTIONAL_UP = "event_directional_up"
    EVENT_DIRECTIONAL_DOWN = "event_directional_down"
    BIDIRECTIONAL_EXPANSION = "bidirectional_expansion"


@dataclass(frozen=True)
class EventUnderlyingHypothesis:
    """One auditable event-to-underlying distribution hypothesis."""

    hypothesis_id: str
    underlying_key: Optional[UnderlyingKey]
    impact_path: Optional[str]
    distribution_mode: Optional[DistributionChangeMode]
    distribution_hypothesis: Optional[str]
    expected_window: Optional[MethodologizedDateRange]
    supporting_statement_ids: Tuple[str, ...] = ()
    contradicting_statement_ids: Tuple[str, ...] = ()
    contradiction_review: Optional[str] = None
    uncertainties: Tuple[str, ...] = ()
    falsification_conditions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        hypothesis_id = _normalize_required_string(
            "hypothesis_id", self.hypothesis_id
        )
        if self.underlying_key is not None:
            _require_underlying_key(self.underlying_key)
        if self.distribution_mode is not None and not isinstance(
            self.distribution_mode, DistributionChangeMode
        ):
            raise TypeError("distribution_mode must be a DistributionChangeMode")
        if self.expected_window is not None:
            _require_date_range("expected_window", self.expected_window)

        supporting = _normalize_id_tuple(
            "supporting_statement_ids", self.supporting_statement_ids
        )
        contradicting = _normalize_id_tuple(
            "contradicting_statement_ids", self.contradicting_statement_ids
        )
        if set(supporting) & set(contradicting):
            raise ValueError(
                "supporting and contradicting statement IDs must be disjoint"
            )

        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        object.__setattr__(
            self, "impact_path", _normalize_optional_string("impact_path", self.impact_path)
        )
        object.__setattr__(
            self,
            "distribution_hypothesis",
            _normalize_optional_string(
                "distribution_hypothesis", self.distribution_hypothesis
            ),
        )
        object.__setattr__(self, "supporting_statement_ids", supporting)
        object.__setattr__(self, "contradicting_statement_ids", contradicting)
        object.__setattr__(
            self,
            "contradiction_review",
            _normalize_optional_string(
                "contradiction_review", self.contradiction_review
            ),
        )
        object.__setattr__(
            self,
            "uncertainties",
            _normalize_text_tuple("uncertainties", self.uncertainties),
        )
        object.__setattr__(
            self,
            "falsification_conditions",
            _normalize_text_tuple(
                "falsification_conditions", self.falsification_conditions
            ),
        )


@dataclass(frozen=True)
class EventIntelligenceSubmission:
    """One Skill-neutral Event Intelligence submission for acceptance."""

    submission_id: str
    event_id: Optional[str]
    producer_id: Optional[str]
    producer_version: Optional[str]
    observed_at: Optional[datetime.datetime]
    event_description: Optional[str]
    event_date_range: Optional[MethodologizedDateRange]
    sources: Tuple[EventSourceReference, ...]
    statements: Tuple[EventStatement, ...]
    hypotheses: Tuple[EventUnderlyingHypothesis, ...]

    def __post_init__(self) -> None:
        submission_id = _normalize_required_string(
            "submission_id", self.submission_id
        )
        if self.event_date_range is not None:
            _require_date_range("event_date_range", self.event_date_range)
        sources = _normalize_record_tuple(
            "sources", self.sources, EventSourceReference, "source_id"
        )
        statements = _normalize_record_tuple(
            "statements", self.statements, EventStatement, "statement_id"
        )
        hypotheses = _normalize_record_tuple(
            "hypotheses",
            self.hypotheses,
            EventUnderlyingHypothesis,
            "hypothesis_id",
        )
        if not hypotheses:
            raise ValueError("hypotheses must contain at least one item")

        for source in sources:
            _require_intrinsic_record(
                "source",
                source,
                EventSourceReference,
                ("source_id", "locator", "title", "published_at"),
            )
        for statement in statements:
            _require_intrinsic_record(
                "statement",
                statement,
                EventStatement,
                (
                    "statement_id",
                    "kind",
                    "text",
                    "source_ids",
                    "dependency_statement_ids",
                ),
            )
        for hypothesis in hypotheses:
            _require_intrinsic_record(
                "hypothesis",
                hypothesis,
                EventUnderlyingHypothesis,
                (
                    "hypothesis_id",
                    "underlying_key",
                    "impact_path",
                    "distribution_mode",
                    "distribution_hypothesis",
                    "expected_window",
                    "supporting_statement_ids",
                    "contradicting_statement_ids",
                    "contradiction_review",
                    "uncertainties",
                    "falsification_conditions",
                ),
            )

        source_ids = {source.source_id for source in sources}
        statement_ids = {statement.statement_id for statement in statements}
        for statement in statements:
            missing_sources = set(statement.source_ids) - source_ids
            if missing_sources:
                raise ValueError(
                    f"statement {statement.statement_id} has dangling source IDs"
                )
            missing_dependencies = (
                set(statement.dependency_statement_ids) - statement_ids
            )
            if missing_dependencies:
                raise ValueError(
                    f"statement {statement.statement_id} has dangling dependencies"
                )
        for hypothesis in hypotheses:
            if set(hypothesis.supporting_statement_ids) - statement_ids:
                raise ValueError(
                    f"hypothesis {hypothesis.hypothesis_id} has dangling support IDs"
                )
            if set(hypothesis.contradicting_statement_ids) - statement_ids:
                raise ValueError(
                    f"hypothesis {hypothesis.hypothesis_id} has dangling contradiction IDs"
                )

        _validate_acyclic_statements(statements)
        observed_at = _normalize_optional_utc_datetime(
            "observed_at", self.observed_at
        )
        if observed_at is not None and any(
            source.published_at is not None
            and source.published_at > observed_at
            for source in sources
        ):
            raise ValueError("source published_at must not be after observed_at")

        object.__setattr__(self, "submission_id", submission_id)
        object.__setattr__(
            self, "event_id", _normalize_optional_string("event_id", self.event_id)
        )
        object.__setattr__(
            self,
            "producer_id",
            _normalize_optional_string("producer_id", self.producer_id),
        )
        object.__setattr__(
            self,
            "producer_version",
            _normalize_optional_string("producer_version", self.producer_version),
        )
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(
            self,
            "event_description",
            _normalize_optional_string("event_description", self.event_description),
        )
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "statements", statements)
        object.__setattr__(self, "hypotheses", hypotheses)


def _validate_acyclic_statements(statements: Iterable[object]) -> None:
    dependencies = {
        statement.statement_id: statement.dependency_statement_ids
        for statement in statements
    }
    states = {statement_id: 0 for statement_id in dependencies}
    for root_id in sorted(dependencies):
        if states[root_id] == 2:
            continue
        stack = [(root_id, False)]
        while stack:
            statement_id, exiting = stack.pop()
            if exiting:
                states[statement_id] = 2
                continue
            if states[statement_id] == 2:
                continue
            if states[statement_id] == 1:
                raise ValueError("statement dependencies must not contain a cycle")
            states[statement_id] = 1
            stack.append((statement_id, True))
            for dependency_id in reversed(dependencies[statement_id]):
                if states[dependency_id] == 1:
                    raise ValueError(
                        "statement dependencies must not contain a cycle"
                    )
                if states[dependency_id] == 0:
                    stack.append((dependency_id, False))


def _require_submission(value: object) -> None:
    _require_intrinsic_record(
        "submission",
        value,
        EventIntelligenceSubmission,
        (
            "submission_id",
            "event_id",
            "producer_id",
            "producer_version",
            "observed_at",
            "event_description",
            "event_date_range",
            "sources",
            "statements",
            "hypotheses",
        ),
    )


class EventIntelligenceAcceptanceStatus(str, Enum):
    """Deterministic status of the Event Intelligence audit boundary."""

    ACCEPTED = "accepted"
    INCOMPLETE = "incomplete"


class EventIntelligenceIssueCode(str, Enum):
    """Closed incomplete-result reasons in canonical declaration order."""

    MISSING_EVENT_ID = "missing_event_id"
    MISSING_PRODUCER_ID = "missing_producer_id"
    MISSING_PRODUCER_VERSION = "missing_producer_version"
    MISSING_OBSERVED_AT = "missing_observed_at"
    MISSING_EVENT_DESCRIPTION = "missing_event_description"
    INCOMPLETE_EVENT_DATE_RANGE = "incomplete_event_date_range"
    NO_STRUCTURED_SOURCES = "no_structured_sources"
    SOURCE_LOCATOR_MISSING = "source_locator_missing"
    NO_STATEMENTS = "no_statements"
    STATEMENT_TEXT_MISSING = "statement_text_missing"
    OBSERVED_FACT_SOURCE_MISSING = "observed_fact_source_missing"
    INTERPRETATION_SOURCE_CLOSURE_MISSING = (
        "interpretation_source_closure_missing"
    )
    MISSING_UNDERLYING_KEY = "missing_underlying_key"
    MISSING_IMPACT_PATH = "missing_impact_path"
    MISSING_DISTRIBUTION_MODE = "missing_distribution_mode"
    MISSING_DISTRIBUTION_HYPOTHESIS = "missing_distribution_hypothesis"
    INCOMPLETE_EXPECTED_WINDOW = "incomplete_expected_window"
    MISSING_SUPPORTING_EVIDENCE = "missing_supporting_evidence"
    MISSING_SUPPORTING_OBSERVED_FACT = "missing_supporting_observed_fact"
    MISSING_SUPPORTING_INTERPRETATION = "missing_supporting_interpretation"
    MISSING_CONTRADICTION_REVIEW = "missing_contradiction_review"
    MISSING_UNCERTAINTIES = "missing_uncertainties"
    MISSING_FALSIFICATION_CONDITIONS = "missing_falsification_conditions"


@dataclass(frozen=True)
class EventIntelligenceAcceptanceIssue:
    """One incomplete reason bound to its source, statement, or hypothesis."""

    code: EventIntelligenceIssueCode
    subject_id: Optional[str] = None

    def __post_init__(self) -> None:
        if type(self.code) is not EventIntelligenceIssueCode:
            raise TypeError("code must be an EventIntelligenceIssueCode")
        object.__setattr__(
            self,
            "subject_id",
            _normalize_optional_string("subject_id", self.subject_id),
        )


def _issue_sort_key(
    issue: EventIntelligenceAcceptanceIssue,
) -> Tuple[int, str]:
    order = {code: index for index, code in enumerate(EventIntelligenceIssueCode)}
    return order[issue.code], issue.subject_id or ""


@dataclass(frozen=True)
class EventIntelligenceAcceptanceResult:
    """Deterministic acceptance result retaining the exact submission."""

    submission: EventIntelligenceSubmission
    status: EventIntelligenceAcceptanceStatus
    issues: Tuple[EventIntelligenceAcceptanceIssue, ...]
    assessment_version: str = _ASSESSMENT_VERSION

    def __post_init__(self) -> None:
        _require_submission(self.submission)
        if type(self.status) is not EventIntelligenceAcceptanceStatus:
            raise TypeError("status must be an EventIntelligenceAcceptanceStatus")
        if type(self.issues) not in {tuple, list}:
            raise TypeError("issues must be a tuple or list")
        issues = tuple(self.issues)
        if not all(
            type(issue) is EventIntelligenceAcceptanceIssue for issue in issues
        ):
            raise TypeError(
                "every issues item must be an EventIntelligenceAcceptanceIssue"
            )
        for issue in issues:
            _require_intrinsic_record(
                "issue",
                issue,
                EventIntelligenceAcceptanceIssue,
                ("code", "subject_id"),
            )
        issue_keys = tuple((issue.code, issue.subject_id) for issue in issues)
        if len(set(issue_keys)) != len(issue_keys):
            raise ValueError("issues must not contain duplicates")
        issues = tuple(sorted(issues, key=_issue_sort_key))
        expected_status = (
            EventIntelligenceAcceptanceStatus.INCOMPLETE
            if issues
            else EventIntelligenceAcceptanceStatus.ACCEPTED
        )
        if self.status is not expected_status:
            raise ValueError("status must agree with whether issues are present")
        if issues != _derive_event_intelligence_issues(self.submission):
            raise ValueError("issues must exactly match the submitted evidence")
        version = _normalize_required_string(
            "assessment_version", self.assessment_version
        )
        if version != _ASSESSMENT_VERSION:
            raise ValueError(
                f"assessment_version must be {_ASSESSMENT_VERSION!r}"
            )
        object.__setattr__(self, "issues", issues)
        object.__setattr__(self, "assessment_version", version)

    @property
    def issue_codes(self) -> Tuple[EventIntelligenceIssueCode, ...]:
        """Return unique issue codes in closed declaration order."""

        selected = {issue.code for issue in self.issues}
        return tuple(code for code in EventIntelligenceIssueCode if code in selected)


def _range_is_incomplete(value: Optional[MethodologizedDateRange]) -> bool:
    return value is None or any(
        item is None
        for item in (value.start_date, value.end_date, value.methodology)
    )


def _statement_closure(
    statement_id: str, statements: Dict[str, EventStatement]
) -> Set[str]:
    closure: Set[str] = set()
    pending = [statement_id]
    while pending:
        current_id = pending.pop()
        if current_id in closure:
            continue
        closure.add(current_id)
        pending.extend(statements[current_id].dependency_statement_ids)
    return closure


def _interpretation_has_source_closure(
    statement: EventStatement, statements: Dict[str, EventStatement]
) -> bool:
    if statement.source_ids:
        return True
    closure = _statement_closure(statement.statement_id, statements)
    return any(
        statements[statement_id].kind is EventStatementKind.OBSERVED_FACT
        and bool(statements[statement_id].source_ids)
        for statement_id in closure
    )


def _derive_event_intelligence_issues(
    submission: EventIntelligenceSubmission,
) -> Tuple[EventIntelligenceAcceptanceIssue, ...]:
    """Derive the canonical semantic-completeness issue tuple."""

    _require_submission(submission)

    issue_keys: Set[Tuple[EventIntelligenceIssueCode, Optional[str]]] = set()

    def add(
        code: EventIntelligenceIssueCode, subject_id: Optional[str] = None
    ) -> None:
        issue_keys.add((code, subject_id))

    if submission.event_id is None:
        add(EventIntelligenceIssueCode.MISSING_EVENT_ID)
    if submission.producer_id is None:
        add(EventIntelligenceIssueCode.MISSING_PRODUCER_ID)
    if submission.producer_version is None:
        add(EventIntelligenceIssueCode.MISSING_PRODUCER_VERSION)
    if submission.observed_at is None:
        add(EventIntelligenceIssueCode.MISSING_OBSERVED_AT)
    if submission.event_description is None:
        add(EventIntelligenceIssueCode.MISSING_EVENT_DESCRIPTION)
    if _range_is_incomplete(submission.event_date_range):
        add(EventIntelligenceIssueCode.INCOMPLETE_EVENT_DATE_RANGE)

    if not submission.sources:
        add(EventIntelligenceIssueCode.NO_STRUCTURED_SOURCES)
    for source in submission.sources:
        if source.locator is None:
            add(EventIntelligenceIssueCode.SOURCE_LOCATOR_MISSING, source.source_id)

    if not submission.statements:
        add(EventIntelligenceIssueCode.NO_STATEMENTS)
    statements = {
        statement.statement_id: statement for statement in submission.statements
    }
    for statement in submission.statements:
        if statement.text is None:
            add(
                EventIntelligenceIssueCode.STATEMENT_TEXT_MISSING,
                statement.statement_id,
            )
        if (
            statement.kind is EventStatementKind.OBSERVED_FACT
            and not statement.source_ids
        ):
            add(
                EventIntelligenceIssueCode.OBSERVED_FACT_SOURCE_MISSING,
                statement.statement_id,
            )
        if (
            statement.kind is EventStatementKind.INTERPRETATION
            and not _interpretation_has_source_closure(statement, statements)
        ):
            add(
                EventIntelligenceIssueCode.INTERPRETATION_SOURCE_CLOSURE_MISSING,
                statement.statement_id,
            )

    for hypothesis in submission.hypotheses:
        subject_id = hypothesis.hypothesis_id
        if hypothesis.underlying_key is None:
            add(EventIntelligenceIssueCode.MISSING_UNDERLYING_KEY, subject_id)
        if hypothesis.impact_path is None:
            add(EventIntelligenceIssueCode.MISSING_IMPACT_PATH, subject_id)
        if hypothesis.distribution_mode is None:
            add(EventIntelligenceIssueCode.MISSING_DISTRIBUTION_MODE, subject_id)
        if hypothesis.distribution_hypothesis is None:
            add(
                EventIntelligenceIssueCode.MISSING_DISTRIBUTION_HYPOTHESIS,
                subject_id,
            )
        if _range_is_incomplete(hypothesis.expected_window):
            add(EventIntelligenceIssueCode.INCOMPLETE_EXPECTED_WINDOW, subject_id)
        if not hypothesis.supporting_statement_ids:
            add(EventIntelligenceIssueCode.MISSING_SUPPORTING_EVIDENCE, subject_id)
        else:
            supporting_closure: Set[str] = set()
            for statement_id in hypothesis.supporting_statement_ids:
                supporting_closure.update(_statement_closure(statement_id, statements))
            if not any(
                statements[statement_id].kind
                is EventStatementKind.OBSERVED_FACT
                and bool(statements[statement_id].source_ids)
                for statement_id in supporting_closure
            ):
                add(
                    EventIntelligenceIssueCode.MISSING_SUPPORTING_OBSERVED_FACT,
                    subject_id,
                )
            if not any(
                statements[statement_id].kind
                is EventStatementKind.INTERPRETATION
                for statement_id in supporting_closure
            ):
                add(
                    EventIntelligenceIssueCode.MISSING_SUPPORTING_INTERPRETATION,
                    subject_id,
                )
        if hypothesis.contradiction_review is None:
            add(EventIntelligenceIssueCode.MISSING_CONTRADICTION_REVIEW, subject_id)
        if not hypothesis.uncertainties:
            add(EventIntelligenceIssueCode.MISSING_UNCERTAINTIES, subject_id)
        if not hypothesis.falsification_conditions:
            add(
                EventIntelligenceIssueCode.MISSING_FALSIFICATION_CONDITIONS,
                subject_id,
            )

    return tuple(
        sorted(
            (
                EventIntelligenceAcceptanceIssue(code, subject_id)
                for code, subject_id in issue_keys
            ),
            key=_issue_sort_key,
        )
    )


def assess_event_intelligence_submission(
    submission: EventIntelligenceSubmission,
) -> EventIntelligenceAcceptanceResult:
    """Assess semantic completeness without external calls or inference."""

    _require_submission(submission)
    issues = _derive_event_intelligence_issues(submission)
    status = (
        EventIntelligenceAcceptanceStatus.INCOMPLETE
        if issues
        else EventIntelligenceAcceptanceStatus.ACCEPTED
    )
    return EventIntelligenceAcceptanceResult(submission, status, issues)
