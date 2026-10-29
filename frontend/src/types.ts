export type View = 'overview' | 'batches' | 'reconciliation' | 'ledger' | 'workbench'
export type Locale = 'en-CA' | 'fr-CA'
export interface User {
  id: string
  username: string
  role: 'operator' | 'approver' | 'auditor'
}
export interface Session {
  user: User
  csrf: string
}
export interface Batch {
  id: string
  name: string
  status: string
  created_at: string
  source_sha256: string
  policy: string
  engine_build: string
  record_count: number
  accepted_count: number
  rejected_count: number
  control_total: string
  payable_total: string
  result_digest: string
  submitted_by: string
  job_id?: string
  records?: Payment[]
  jobs?: Job[]
  errors?: unknown[]
  approval?: unknown
}
export interface Payment {
  id: string
  batch_id: string
  position: number
  source: string
  reference: string
  program: string
  business_date: string
  eligible_cost: string
  beneficiary: string
  beneficiary_names?: Record<Locale, string>
  reason: string
  payable: string | null
  trace: {
    rate?: string
    unrounded?: string
    rounded?: string
    cap?: string
    [key: string]: unknown
  }
  proposal: { debit: string; credit: string; amount: string } | null
  raw_hex: string
  state: string
}
export interface Journal {
  id: string
  kind: string
  source: string
  reference: string
  amount: string
  debit: string
  credit: string
  currency: string
  created_at: string
  reversal_of?: string
  batch_id: string
  record_id: string
}
export interface Attempt {
  id?: string
  attempt?: number
  started_at?: string
  finished_at?: string
  status?: string
  outcome?: string
  error?: string
  [key: string]: unknown
}
export interface Job {
  id: string
  kind: string
  status: string
  completed: number
  total: number
  attempts: Attempt[]
  error?: string
  failure_mode?: string
  result?: {
    same?: boolean
    original_digest?: string
    replay_digest?: string
    differences?: unknown[]
    v1_total?: string
    v2_total?: string
    delta?: string
    [key: string]: unknown
  }
}
export interface Audit {
  id: string
  action: string
  actor: string
  created_at: string
  payload?: unknown
  event?: string
}
export interface Overview {
  metrics: {
    calculated: string
    approved: string
    posted: string
    settled: string
    outstanding: string
    exceptions: number
    batches: number
  }
  recent_batches: Batch[]
  health: {
    engine: string | boolean
    worker: string | boolean
    engine_build: string
    demo?: boolean
  }
  activity: Audit[]
}
export interface Reconciliation {
  id: string
  reference: string
  source?: string
  settlement_reference: string
  expected: string | null
  received: string | null
  classification: string
  state?: string
  disposition?: string
  actor?: string
  accepted?: boolean
  record_id?: string
}
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
export interface Trace {
  record: Payment
  batch: Batch
  journals: Journal[]
  attempts: Attempt[]
  source_url: string
}
