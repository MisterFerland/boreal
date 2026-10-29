"""Typed public responses. Financial JSON values are strings, never floats."""

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Money = Annotated[str, StringConstraints(pattern=r"^-?\d+\.\d{2}$")]
T = TypeVar("T")


class Contract(BaseModel):
    model_config = ConfigDict(extra="allow")


class Batch(Contract):
    id: str
    name: str
    status: Literal["queued", "calculating", "review", "quarantined", "failed", "approved", "posting", "posted"]
    created_at: str
    source_sha256: str
    schema_version: str
    policy: Literal["V1"]
    engine_build: str | None
    record_count: int
    accepted_count: int
    rejected_count: int
    control_total: Money | None
    payable_total: Money | None
    result_digest: str | None
    proposal_digest: str | None
    submitted_by: str
    job_id: str | None
    errors: list


class Proposal(Contract):
    debit: Literal["5100", "2100", "1100"]
    credit: Literal["5100", "2100", "1100"]
    amount: Money


class Record(Contract):
    id: str
    batch_id: str
    position: int
    source: str
    reference: str
    program: str
    business_date: str
    eligible_cost: Money | None
    beneficiary: str
    reason: str
    payable: Money | None
    trace: dict
    proposal: Proposal | None
    raw_hex: str
    state: Literal["accepted", "rejected", "posted", "settled", "reversed"]


class Job(Contract):
    id: str
    kind: Literal["calculate", "post", "replay", "compare", "reconcile"]
    status: Literal["queued", "running", "retry", "failed", "succeeded"]
    completed: int
    total: int
    attempts: list[dict]
    result: dict | None
    error: str | None


class BatchDetail(Batch):
    records: list[Record]
    jobs: list[Job]
    approval: dict | None


class Journal(Contract):
    id: str
    kind: Literal["obligation", "settlement", "reversal"]
    batch_id: str
    record_id: str
    source: str
    reference: str
    amount: Money
    debit: Literal["5100", "2100", "1100"]
    credit: Literal["5100", "2100", "1100"]
    currency: Literal["CAD"]
    created_at: str
    reversal_of: str | None


class Reconciliation(Contract):
    id: str
    reference: str
    settlement_reference: str | None
    expected: Money | None
    received: Money | None
    classification: Literal["MATCH", "AMOUNT_MISMATCH", "DUPLICATE", "MISSING", "UNEXPECTED"]
    state: Literal["open", "reviewed", "accepted"]
    disposition: str | None
    actor: str | None


class Page(Contract, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class Metrics(Contract):
    calculated: Money
    approved: Money
    posted: Money
    settled: Money
    outstanding: Money
    exceptions: int
    batches: int


class Overview(Contract):
    metrics: Metrics
    recent_batches: list[Batch]
    health: dict
    activity: list[dict]


class Trace(Contract):
    record: Record
    batch: Batch
    journals: list[Journal]
    attempts: list[dict]
    source_url: str
