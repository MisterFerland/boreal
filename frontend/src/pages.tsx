import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Braces,
  Check,
  CheckCheck,
  ChevronRight,
  Clock3,
  Download,
  FileCode2,
  FileStack,
  Fingerprint,
  GitCompareArrows,
  History,
  Info,
  ListFilter,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { api, post } from './api'
import { useResource, useStoredState } from './hooks'
import type {
  Batch,
  Job,
  Journal,
  Locale,
  Page,
  Payment,
  Reconciliation,
  Trace,
  User,
  Audit,
} from './types'
import { date, money, short } from './format'
import {
  AuditAction,
  Dialog,
  Empty,
  ErrorNotice,
  JobKind,
  KeyValue,
  Loading,
  Pagination,
  Panel,
  Reason,
  Status,
  useText,
} from './ui'

function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string
  title: string
  description: string
  children?: React.ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow heading-eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  )
}
function SearchField({
  value,
  onChange,
  label,
}: {
  value: string
  onChange: (value: string) => void
  label: string
}) {
  return (
    <div className="filter-search">
      <Search size={17} />
      <input
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

export function Batches({
  locale,
  revision,
  search,
  setSearch,
  onBatch,
  onImport,
  canImport,
}: {
  locale: Locale
  revision: number
  search: string
  setSearch: (value: string) => void
  onBatch: (id: string) => void
  onImport: () => void
  canImport: boolean
}) {
  const t = useText()
  const [page, setPage] = useStoredState('batches.page', 1)
  const [status, setStatus] = useStoredState('batches.status', '')
  const [sort, setSort] = useStoredState('batches.sort', 'created_at')
  const resource = useResource<Page<Batch>>(
    `/batches?q=${encodeURIComponent(search)}&status=${status}&page=${page}&page_size=15&sort=${sort}`,
    revision,
    true,
  )
  return (
    <>
      <PageHeading
        eyebrow={t('SOURCE TO LEDGER', 'DE LA SOURCE AU GRAND LIVRE')}
        title={t('Batch operations', 'Opérations par lots')}
        description={t(
          'Import, review and authorize with a complete chain of evidence.',
          'Importez, examinez et autorisez avec une chaîne de preuves complète.',
        )}
      >
        <button className="button primary" disabled={!canImport} onClick={onImport}>
          <Plus size={18} />
          {t('Import batch', 'Importer un lot')}
        </button>
      </PageHeading>
      <ErrorNotice error={resource.error} />
      <div className="panel">
        <div className="table-toolbar">
          <SearchField
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            label={t('Search batch or reference…', 'Rechercher un lot ou une référence…')}
          />
          <div className="toolbar-filters">
            <label className="select-wrap">
              <ListFilter size={15} />
              <span className="sr-only">{t('Filter status', 'Filtrer par état')}</span>
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value)
                  setPage(1)
                }}
              >
                <option value="">{t('All statuses', 'Tous les états')}</option>
                <option value="review">{t('Ready for review', 'À examiner')}</option>
                <option value="approved">{t('Approved', 'Approuvé')}</option>
                <option value="posted">{t('Posted', 'Comptabilisé')}</option>
                <option value="quarantined">{t('Quarantined', 'En quarantaine')}</option>
                <option value="failed">{t('Failed', 'Échec')}</option>
              </select>
            </label>
            <label className="select-wrap">
              <span className="sr-only">{t('Sort batches', 'Trier les lots')}</span>
              <select value={sort} onChange={(event) => setSort(event.target.value)}>
                <option value="created_at">{t('Newest first', 'Plus récents')}</option>
                <option value="name">{t('Batch name', 'Nom du lot')}</option>
              </select>
            </label>
          </div>
        </div>
        {resource.loading ? (
          <Loading />
        ) : resource.data?.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('Batch', 'Lot')}</th>
                  <th>{t('Status', 'État')}</th>
                  <th>{t('Policy', 'Politique')}</th>
                  <th className="numeric">{t('Records', 'Enregistrements')}</th>
                  <th className="numeric">{t('Payable', 'À payer')}</th>
                  <th>{t('Imported', 'Importé')}</th>
                  <th className="table-action">
                    <span className="sr-only">{t('Open', 'Ouvrir')}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {resource.data.items.map((batch) => (
                  <tr key={batch.id}>
                    <td>
                      <button className="record-link" onClick={() => onBatch(batch.id)}>
                        <span className="file-tile">
                          <FileStack size={17} />
                        </span>
                        <span>
                          <strong>{batch.name}</strong>
                          <small className="mono">{short(batch.source_sha256, 16)}</small>
                        </span>
                      </button>
                    </td>
                    <td>
                      <Status value={batch.status} />
                    </td>
                    <td>
                      <span className="policy-pill">{batch.policy || 'V1'}</span>
                    </td>
                    <td className="numeric">
                      <strong>{batch.record_count || 0}</strong>
                      {!!batch.rejected_count && (
                        <small className="rejected-count">
                          {batch.rejected_count} {t('rejected', 'rejetés')}
                        </small>
                      )}
                    </td>
                    <td className="numeric amount">{money(batch.payable_total, locale)}</td>
                    <td className="muted nowrap">{date(batch.created_at, locale)}</td>
                    <td>
                      <button
                        className="icon-button"
                        onClick={() => onBatch(batch.id)}
                        aria-label={`${t('Open batch', 'Ouvrir le lot')} ${batch.name}`}
                      >
                        <ChevronRight size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title={t('No matching batches', 'Aucun lot correspondant')}>
            {t(
              'Import a synthetic batch or adjust your search and filters.',
              'Importez un lot synthétique ou modifiez la recherche et les filtres.',
            )}
          </Empty>
        )}
        <Pagination data={resource.data} onPage={setPage} />
      </div>
      <div className="bottom-note">
        <ShieldCheck size={17} />
        {t(
          'A file is validated before approval. Only separately authorized proposals can enter the ledger.',
          'Un fichier est validé avant l’approbation. Seules les propositions autorisées séparément peuvent être comptabilisées.',
        )}
      </div>
    </>
  )
}

export function BatchDetail({
  id,
  locale,
  user,
  demo,
  onClose,
  onTrace,
  refresh,
  suspended = false,
}: {
  id: string
  locale: Locale
  user: User
  demo: boolean
  onClose: () => void
  onTrace: (id: string) => void
  refresh: () => void
  suspended?: boolean
}) {
  const t = useText()
  const detail = useResource<Batch>(`/batches/${id}`, 0, true)
  const [page, setPage] = useState(1)
  const rows = useResource<Page<Payment>>(
    `/batches/${id}/records?page=${page}&page_size=12`,
    0,
    true,
  )
  const [error, setError] = useState<Error | null>(null)
  const [busy, setBusy] = useState(false)
  const [failureMode, setFailureMode] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useResource<Job>(jobId ? `/jobs/${jobId}` : null, 0, true)
  const batch = detail.data
  const action = async (kind: 'approve' | 'post' | 'replay' | 'compare') => {
    setBusy(true)
    setError(null)
    try {
      const result = await post<Batch | Job>(
        `/batches/${id}/${kind}`,
        kind === 'post' ? { failure_mode: failureMode || undefined } : {},
      )
      if (kind !== 'approve') setJobId(result.id)
      detail.refresh()
      rows.refresh()
      refresh()
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  const retry = async (jobIdToRetry: string) => {
    try {
      await post(`/jobs/${jobIdToRetry}/retry`)
      detail.refresh()
      refresh()
    } catch (cause) {
      setError(cause as Error)
    }
  }
  const records = rows.data?.items || batch?.records || []
  return (
    <Dialog
      title={batch?.name || t('Batch detail', 'Détail du lot')}
      subtitle={t(
        'IMMUTABLE SOURCE · REVIEWABLE RESULTS',
        'SOURCE CONSERVÉE · RÉSULTATS VÉRIFIABLES',
      )}
      onClose={onClose}
      drawer
      suspended={suspended}
    >
      <div className="dialog-body batch-detail">
        <ErrorNotice error={error || detail.error || rows.error} />
        {!batch ? (
          <Loading />
        ) : (
          <>
            <div className="detail-status-row">
              <Status value={batch.status} />
              <span className="muted">
                {date(batch.created_at, locale)}
                <span> · </span>
                {batch.policy}
              </span>
            </div>
            <div className="detail-stats">
              <div>
                <span>{t('Calculated payable', 'Montant calculé')}</span>
                <strong>{money(batch.payable_total, locale)}</strong>
              </div>
              <div>
                <span>{t('Accepted', 'Acceptés')}</span>
                <strong>
                  {batch.accepted_count || 0}
                  <small> / {batch.record_count || 0}</small>
                </strong>
              </div>
              <div>
                <span>{t('Rejected', 'Rejetés')}</span>
                <strong className={batch.rejected_count ? 'warning-text' : ''}>
                  {batch.rejected_count || 0}
                </strong>
              </div>
            </div>
            <div className="metadata-grid">
              <KeyValue label={t('Source control total', 'Total de contrôle source')}>
                {money(batch.control_total, locale)}
              </KeyValue>
              <KeyValue label={t('Submitted by', 'Soumis par')}>{batch.submitted_by}</KeyValue>
              <KeyValue label={t('Input SHA-256', 'SHA-256 d’entrée')} mono>
                {batch.source_sha256}
              </KeyValue>
              <KeyValue label={t('Result digest', 'Empreinte du résultat')} mono>
                {batch.result_digest}
              </KeyValue>
            </div>
            {!!batch.errors?.length && (
              <div className="error-notice" role="alert">
                <Info size={18} />
                <div>
                  <strong>{t('Validation findings', 'Résultats de validation')}</strong>
                  {batch.errors.map((value, index) => (
                    <p key={index}>
                      <Reason code={typeof value === 'string' ? value : JSON.stringify(value)} />
                    </p>
                  ))}
                </div>
              </div>
            )}
            {batch.status === 'review' && (
              <div className="approval-callout">
                <ShieldCheck size={23} />
                <div>
                  <strong>
                    {t('Ready for an independent review', 'Prêt pour un examen indépendant')}
                  </strong>
                  <p>
                    {t(
                      `${batch.accepted_count} accepted instructions and ${batch.rejected_count} rejected. Approval binds this input, policy and result.`,
                      `${batch.accepted_count} instructions acceptées et ${batch.rejected_count} rejetées. L’approbation lie cette entrée, cette politique et ce résultat.`,
                    )}
                  </p>
                  <button
                    className="button primary"
                    disabled={
                      busy ||
                      user.role !== 'approver' ||
                      batch.submitted_by === user.id ||
                      !batch.accepted_count
                    }
                    onClick={() => void action('approve')}
                  >
                    {t('Approve proposals', 'Approuver les propositions')}
                    <ArrowRight size={16} />
                  </button>
                  {(user.role !== 'approver' || batch.submitted_by === user.id) && (
                    <small>
                      {t(
                        'Sign in with a separate approver account to authorize this batch.',
                        'Connectez-vous avec un autre compte approbateur pour autoriser ce lot.',
                      )}
                    </small>
                  )}
                </div>
              </div>
            )}
            {batch.status === 'approved' && (
              <div className="approval-callout">
                <CheckCheck size={23} />
                <div>
                  <strong>
                    {t('Approved and ready to post', 'Approuvé et prêt à comptabiliser')}
                  </strong>
                  <p>
                    {t(
                      'The worker will commit the approved proposals in durable, atomic chunks.',
                      'Le processus inscrira les propositions approuvées par segments atomiques et durables.',
                    )}
                  </p>
                  {demo && (
                    <label className="failure-control">
                      {t('Local interruption demonstration', 'Démonstration d’interruption locale')}
                      <select
                        value={failureMode}
                        onChange={(event) => setFailureMode(event.target.value)}
                      >
                        <option value="">{t('Normal processing', 'Traitement normal')}</option>
                        <option value="before_commit">
                          {t('Interrupt before commit', 'Interrompre avant la validation')}
                        </option>
                        <option value="after_commit">
                          {t('Interrupt after commit', 'Interrompre après la validation')}
                        </option>
                      </select>
                    </label>
                  )}
                  <button
                    className="button primary"
                    disabled={busy || user.role !== 'approver'}
                    onClick={() => void action('post')}
                  >
                    <Play size={16} />
                    {t('Post approved batch', 'Comptabiliser le lot approuvé')}
                  </button>
                </div>
              </div>
            )}
            <div className="section-heading">
              <h3>{t('Instructions', 'Instructions')}</h3>
              <span className="muted">
                {t(
                  'Select a reference to trace its payment',
                  'Sélectionnez une référence pour suivre le paiement',
                )}
              </span>
            </div>
            {records.length ? (
              <div className="table-scroll compact-table">
                <table>
                  <thead>
                    <tr>
                      <th>{t('Reference', 'Référence')}</th>
                      <th>{t('Decision', 'Décision')}</th>
                      <th className="numeric">{t('Eligible cost', 'Coût admissible')}</th>
                      <th className="numeric">{t('Payable', 'À payer')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((record) => (
                      <tr key={record.id || record.position}>
                        <td>
                          <button className="text-link mono" onClick={() => onTrace(record.id)}>
                            {record.reference}
                            <ArrowUpRight size={13} />
                          </button>
                          <small className="table-subtext">{record.source}</small>
                        </td>
                        <td>
                          <span
                            className={`reason-label ${record.reason === 'ACCEPTED' ? 'positive' : 'warning-text'}`}
                          >
                            <Reason code={record.reason} />
                          </span>
                        </td>
                        <td className="numeric amount">{money(record.eligible_cost, locale)}</td>
                        <td className="numeric amount">{money(record.payable, locale)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty />
            )}
            <Pagination data={rows.data} onPage={setPage} />
            <div className="section-heading">
              <h3>{t('Processing & attempts', 'Traitement et tentatives')}</h3>
              <span className="live-label">
                <span className="status-dot" />
                {t('Refreshes every 5 seconds', 'Actualisation toutes les 5 secondes')}
              </span>
            </div>
            {batch.jobs?.length ? (
              <div className="jobs-list">
                {batch.jobs.map((item) => (
                  <div className="job-card" key={item.id}>
                    <div>
                      <span>
                        <JobKind kind={item.kind} />
                      </span>
                      <Status value={item.status} />
                    </div>
                    <progress
                      max={item.total || 1}
                      value={item.completed || 0}
                      aria-label={t('Job progress', 'Progression du traitement')}
                    />
                    <div>
                      <span className="muted">
                        {item.completed || 0} / {item.total || 0} {t('records', 'enregistrements')}
                      </span>
                      <span className="muted">
                        {item.attempts?.length || 0} {t('attempts', 'tentatives')}
                      </span>
                      {['failed', 'retry'].includes(item.status) && (
                        <button className="text-link" onClick={() => void retry(item.id)}>
                          <RefreshCw size={13} />
                          {t('Retry', 'Réessayer')}
                        </button>
                      )}
                    </div>
                    {item.error && <p className="job-error">{item.error}</p>}
                    {item.attempts?.map((attempt, index) => (
                      <div className="attempt" key={attempt.id || index}>
                        <Clock3 size={13} />
                        <span>
                          {t('Attempt', 'Tentative')} {index + 1}
                        </span>
                        <span>{date(attempt.started_at, locale)}</span>
                        <code>{attempt.outcome || attempt.status || attempt.error || '—'}</code>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">
                {t('No processing attempts yet.', 'Aucune tentative de traitement pour le moment.')}
              </p>
            )}
            <div className="section-heading">
              <h3>{t('Verify without changing history', 'Vérifier sans modifier l’historique')}</h3>
            </div>
            <div className="action-grid">
              <button
                className="button secondary"
                disabled={busy || !batch.result_digest}
                onClick={() => void action('replay')}
              >
                <RotateCcw size={16} />
                {t('Replay frozen input', 'Rejouer l’entrée figée')}
              </button>
              <button
                className="button secondary"
                disabled={busy || !batch.result_digest}
                onClick={() => void action('compare')}
              >
                <GitCompareArrows size={16} />
                {t('Compare V1 / V2', 'Comparer V1 / V2')}
              </button>
              {user.role === 'auditor' && (
                <a className="button secondary" href={`/api/batches/${id}/evidence`} download>
                  <Download size={16} />
                  {t('Export evidence ZIP', 'Exporter les preuves ZIP')}
                </a>
              )}
            </div>
            {user.role !== 'auditor' && (
              <p className="hint">
                {t(
                  'Evidence export is available to the auditor account.',
                  'L’exportation des preuves est accessible au compte auditeur.',
                )}
              </p>
            )}
            {jobId && <JobResult job={job.data} locale={locale} error={job.error} />}
          </>
        )}
      </div>
    </Dialog>
  )
}

function JobResult({
  job,
  locale,
  error,
}: {
  job: Job | null
  locale: Locale
  error: Error | null
}) {
  const t = useText()
  if (error) return <ErrorNotice error={error} />
  if (!job) return <Loading />
  return (
    <div className="result-card" aria-live="polite">
      <div className="result-card-title">
        <Braces size={18} />
        <strong>
          {job.kind === 'compare'
            ? t('Policy comparison', 'Comparaison des politiques')
            : t('Historical replay', 'Rejeu historique')}
        </strong>
        <Status value={job.status} />
      </div>
      {job.error && <p className="warning-text">{job.error}</p>}
      {job.result && (
        <>
          {job.result.same !== undefined && (
            <p className={job.result.same ? 'positive' : 'warning-text'}>
              {job.result.same
                ? t(
                    'Recomputed results match the original financial digest.',
                    'Les résultats recalculés correspondent à l’empreinte financière d’origine.',
                  )
                : t(
                    'Differences detected. Inspect the exact results below.',
                    'Des différences ont été détectées. Examinez les résultats exacts ci-dessous.',
                  )}
            </p>
          )}
          {job.result.v1_total !== undefined && (
            <div className="detail-stats">
              <div>
                <span>V1 · 75%</span>
                <strong>{money(job.result.v1_total, locale)}</strong>
              </div>
              <div>
                <span>V2 · 80%</span>
                <strong>{money(job.result.v2_total, locale)}</strong>
              </div>
              <div>
                <span>{t('Difference', 'Écart')}</span>
                <strong>{money(job.result.delta, locale)}</strong>
              </div>
            </div>
          )}
          <details>
            <summary>{t('Inspect result payload', 'Examiner les résultats détaillés')}</summary>
            <pre>{JSON.stringify(job.result, null, 2)}</pre>
          </details>
        </>
      )}
      <small className="muted">
        {t(
          'Read-only verification. No journal is posted.',
          'Vérification en lecture seule. Aucune écriture n’est comptabilisée.',
        )}
      </small>
    </div>
  )
}

export function TraceDrawer({
  id,
  locale,
  onClose,
}: {
  id: string
  locale: Locale
  onClose: () => void
}) {
  const t = useText()
  const resource = useResource<Trace>(`/records/${id}/trace`)
  const [tab, setTab] = useState<'calculation' | 'bytes' | 'journal'>('calculation')
  const [field, setField] = useState(5)
  const result = resource.data
  const record = result?.record
  const fields =
    record?.raw_hex?.length === 146
      ? [
          {
            name: 'SOURCE-SYSTEM',
            start: 0,
            length: 8,
            pic: 'PIC X(8)',
            en: 'Source system',
            fr: 'Système source',
          },
          {
            name: 'INSTRUCTION-REF',
            start: 8,
            length: 20,
            pic: 'PIC X(20)',
            en: 'Instruction reference',
            fr: 'Référence d’instruction',
          },
          {
            name: 'PROGRAM-CODE',
            start: 28,
            length: 4,
            pic: 'PIC X(4)',
            en: 'Program code',
            fr: 'Code de programme',
          },
          {
            name: 'BUSINESS-DATE',
            start: 32,
            length: 8,
            pic: 'PIC X(8)',
            en: 'Business date',
            fr: 'Date opérationnelle',
          },
          {
            name: 'ELIGIBLE-COST',
            start: 40,
            length: 5,
            pic: 'PIC S9(7)V99 COMP-3',
            en: 'Eligible cost',
            fr: 'Coût admissible',
          },
          {
            name: 'BENEFICIARY-ID',
            start: 45,
            length: 28,
            pic: 'PIC X(28)',
            en: 'Beneficiary identifier',
            fr: 'Identifiant du bénéficiaire',
          },
        ]
      : [
          {
            name: 'RECORD-TYPE',
            start: 0,
            length: 1,
            pic: 'PIC X',
            en: 'Record type',
            fr: 'Type d’enregistrement',
          },
          {
            name: 'SOURCE-SYSTEM',
            start: 1,
            length: 8,
            pic: 'PIC X(8)',
            en: 'Source system',
            fr: 'Système source',
          },
          {
            name: 'INSTRUCTION-REF',
            start: 9,
            length: 20,
            pic: 'PIC X(20)',
            en: 'Instruction reference',
            fr: 'Référence d’instruction',
          },
          {
            name: 'PROGRAM-CODE',
            start: 29,
            length: 4,
            pic: 'PIC X(4)',
            en: 'Program code',
            fr: 'Code de programme',
          },
          {
            name: 'BUSINESS-DATE',
            start: 33,
            length: 8,
            pic: 'PIC X(8)',
            en: 'Business date',
            fr: 'Date opérationnelle',
          },
          {
            name: 'ELIGIBLE-COST',
            start: 41,
            length: 11,
            pic: 'PIC X(11)',
            en: 'Eligible cost',
            fr: 'Coût admissible',
          },
          {
            name: 'BENEFICIARY-ID',
            start: 52,
            length: 28,
            pic: 'PIC X(28)',
            en: 'Beneficiary identifier',
            fr: 'Identifiant du bénéficiaire',
          },
        ]
  const bytes = record?.raw_hex?.match(/.{2}/g) || []
  const selected = fields[field] || fields[0]
  const mixed = bytes.length === 73
  const decodedValues: Record<string, string> = {
    'SOURCE-SYSTEM': record?.source || '',
    'INSTRUCTION-REF': record?.reference || '',
    'PROGRAM-CODE': record?.program || '',
    'BUSINESS-DATE': record?.business_date || '',
    'ELIGIBLE-COST': record?.eligible_cost || '',
    'BENEFICIARY-ID': record?.beneficiary || '',
  }
  return (
    <Dialog
      title={t('Trace this payment', 'Suivre ce paiement')}
      subtitle={record?.reference || t('LOADING REFERENCE', 'CHARGEMENT DE LA RÉFÉRENCE')}
      onClose={onClose}
      drawer
    >
      <div className="dialog-body trace-body">
        <ErrorNotice error={resource.error} />
        {!result || !record ? (
          <Loading />
        ) : (
          <>
            <div className="trace-hero">
              <span className="trace-fingerprint">
                <Fingerprint size={30} />
              </span>
              <div>
                <span>
                  {record.beneficiary_names?.[locale] || record.beneficiary || record.reference}
                </span>
                <h3>{money(record.payable, locale)}</h3>
                <span className="mono">
                  {record.source} / {record.reference}
                </span>
              </div>
              <Status value={record.state || record.reason} />
            </div>
            <div
              className="trace-tabs"
              role="tablist"
              aria-label={t('Payment trace details', 'Détails de la trace du paiement')}
            >
              {[
                { id: 'calculation', en: 'Calculation', fr: 'Calcul', icon: Braces },
                { id: 'bytes', en: 'Source bytes', fr: 'Octets sources', icon: FileCode2 },
                {
                  id: 'journal',
                  en: 'Ledger & attempts',
                  fr: 'Écritures et tentatives',
                  icon: History,
                },
              ].map((item) => (
                <button
                  key={item.id}
                  role="tab"
                  id={`tab-${item.id}`}
                  aria-selected={tab === item.id}
                  aria-controls={`panel-${item.id}`}
                  tabIndex={tab === item.id ? 0 : -1}
                  onKeyDown={(event) => {
                    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End']
                    if (!keys.includes(event.key)) return
                    event.preventDefault()
                    const tabs = ['calculation', 'bytes', 'journal'] as const
                    const current = tabs.indexOf(tab)
                    const next =
                      event.key === 'Home'
                        ? 0
                        : event.key === 'End'
                          ? 2
                          : (current + (event.key === 'ArrowRight' ? 1 : 2)) % 3
                    setTab(tabs[next])
                    const buttons =
                      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(
                        '[role="tab"]',
                      )
                    buttons?.[next]?.focus()
                  }}
                  onClick={() => setTab(item.id as typeof tab)}
                >
                  <item.icon size={16} />
                  {t(item.en, item.fr)}
                </button>
              ))}
            </div>
            {tab === 'calculation' && (
              <section role="tabpanel" id="panel-calculation" aria-labelledby="tab-calculation">
                <div className="section-heading">
                  <h3>{t('The calculation, step by step', 'Le calcul, étape par étape')}</h3>
                  <span className="policy-pill">
                    {String(record.trace?.rule_id || `CIR-${result.batch.policy}`)}
                  </span>
                </div>
                <div className="calculation-steps">
                  <CalculationStep
                    number="01"
                    title={t('Pre-approved eligible cost', 'Coût admissible préapprouvé')}
                    value={money(record.eligible_cost, locale)}
                    note={t(
                      'Decoded from the original source record.',
                      'Décodé à partir de l’enregistrement source original.',
                    )}
                  />
                  <CalculationStep
                    number="02"
                    title={t('Apply the reimbursement rate', 'Appliquer le taux de remboursement')}
                    value={`× ${record.trace?.rate || '—'}`}
                    note={`${record.eligible_cost} × ${record.trace?.rate || '—'} = ${record.trace?.unrounded || '—'}`}
                  />
                  <CalculationStep
                    number="03"
                    title={t('Round half up to cents', 'Arrondir à la hausse à un demi-cent')}
                    value={money(record.trace?.rounded, locale)}
                    note={t(
                      'The rounding point is explicit in the COBOL rule.',
                      'Le point d’arrondi est explicite dans la règle COBOL.',
                    )}
                  />
                  <CalculationStep
                    number="04"
                    title={t('Apply the program cap', 'Appliquer le plafond du programme')}
                    value={money(record.payable, locale)}
                    note={`${t('Maximum reimbursement', 'Remboursement maximal')} ${money(record.trace?.cap, locale)}`}
                    final
                  />
                </div>
                <div className="metadata-grid">
                  <KeyValue label={t('Engine decision', 'Décision du moteur')}>
                    <Reason code={record.reason} />
                  </KeyValue>
                  <KeyValue label={t('Business date', 'Date opérationnelle')}>
                    {record.business_date}
                  </KeyValue>
                  <KeyValue label={t('Engine build', 'Version du moteur')} mono>
                    {result.batch.engine_build}
                  </KeyValue>
                  <KeyValue label={t('Source position', 'Position source')}>
                    {t('Physical record', 'Enregistrement physique')} {record.position}
                  </KeyValue>
                </div>
                <a
                  className="source-link"
                  href={result.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileCode2 size={20} />
                  <span>
                    <strong>
                      {t('Inspect the actual COBOL source', 'Examiner le code COBOL réel')}
                    </strong>
                    <small>
                      {t(
                        'Allowlisted source for this recorded build',
                        'Code autorisé de cette version conservée',
                      )}
                    </small>
                  </span>
                  <ArrowUpRight size={18} />
                </a>
              </section>
            )}
            {tab === 'bytes' && (
              <section role="tabpanel" id="panel-bytes" aria-labelledby="tab-bytes">
                <div className="section-heading">
                  <h3>{t('Original bytes', 'Octets originaux')}</h3>
                  <span className="mono">
                    {bytes.length} B · {mixed ? 'IBM-037 / COMP-3' : 'ASCII v1'}
                  </span>
                </div>
                <p className="lead-copy">
                  {t(
                    'Select a field to highlight its exact byte boundaries. Offsets are zero-based. Original bytes are preserved without transformation.',
                    'Sélectionnez un champ pour mettre en évidence ses limites exactes. Les décalages commencent à zéro. Les octets originaux sont conservés sans transformation.',
                  )}
                </p>
                <div className="hex-inspector">
                  <div className="hex-heading">
                    <span>OFFSET</span>
                    <span>HEX</span>
                    <span>{t('PRINTABLE', 'IMPRIMABLE')}</span>
                  </div>
                  {Array.from({ length: Math.ceil(bytes.length / 16) }, (_, row) => (
                    <div className="hex-row" key={row}>
                      <span className="hex-offset">
                        {(row * 16).toString(16).padStart(4, '0').toUpperCase()}
                      </span>
                      <div className="hex-values">
                        {bytes.slice(row * 16, row * 16 + 16).map((byte, col) => {
                          const pos = row * 16 + col
                          return (
                            <span
                              className={
                                pos >= selected.start && pos < selected.start + selected.length
                                  ? 'highlight'
                                  : ''
                              }
                              key={pos}
                            >
                              {byte.toUpperCase()}
                            </span>
                          )
                        })}
                      </div>
                      <span className="ascii-values">
                        {bytes
                          .slice(row * 16, row * 16 + 16)
                          .map((byte) => {
                            const code = parseInt(byte, 16)
                            return code >= 32 && code <= 126 ? String.fromCharCode(code) : '·'
                          })
                          .join('')}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="field-grid">
                  {fields.map((item, index) => (
                    <button
                      className={field === index ? 'selected' : ''}
                      key={item.name}
                      onClick={() => setField(index)}
                    >
                      <span>{t(item.en, item.fr)}</span>
                      <code>
                        {item.start}–{item.start + item.length - 1}
                      </code>
                    </button>
                  ))}
                </div>
                <div className="copybook-card">
                  <div>
                    <span className="eyebrow">COPYBOOK · {mixed ? 'MIXED-V1' : 'ASCII-V1'}</span>
                    <code>
                      05 {selected.name} {selected.pic}.
                    </code>
                  </div>
                  <KeyValue label={t('Decoded value', 'Valeur décodée')} mono>
                    {mixed
                      ? decodedValues[selected.name]
                      : bytes
                          .slice(selected.start, selected.start + selected.length)
                          .map((byte) => String.fromCharCode(parseInt(byte, 16)))
                          .join('')}
                  </KeyValue>
                </div>
                <KeyValue label={t('Original input SHA-256', 'SHA-256 de l’entrée originale')} mono>
                  {result.batch.source_sha256}
                </KeyValue>
              </section>
            )}
            {tab === 'journal' && (
              <section role="tabpanel" id="panel-journal" aria-labelledby="tab-journal">
                <div className="section-heading">
                  <h3>{t('Journal trail', 'Historique des écritures')}</h3>
                  <Status value={record.state} />
                </div>
                {result.journals?.length ? (
                  result.journals.map((journal) => (
                    <div className="journal-card" key={journal.id}>
                      <div>
                        <strong>{journal.kind}</strong>
                        <span className="mono">{short(journal.id)}</span>
                      </div>
                      <div className="journal-lines">
                        <div>
                          <span>
                            {t('Debit', 'Débit')} · {account(journal.debit, t)}
                          </span>
                          <strong>{money(journal.amount, locale)}</strong>
                        </div>
                        <div>
                          <span>
                            {t('Credit', 'Crédit')} · {account(journal.credit, t)}
                          </span>
                          <strong>{money(journal.amount, locale)}</strong>
                        </div>
                      </div>
                      <div className="journal-bottom">
                        <span>
                          <Check size={14} />
                          {t('Balanced in CAD', 'Équilibré en CAD')}
                        </span>
                        <span>{date(journal.created_at, locale)}</span>
                      </div>
                      {journal.reversal_of && (
                        <p className="mono">
                          {t('Reverses', 'Contrepasse')} {journal.reversal_of}
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <Empty title={t('No posted journal', 'Aucune écriture comptabilisée')}>
                    {t(
                      'The calculated proposal will be posted only after independent approval.',
                      'La proposition calculée sera comptabilisée uniquement après une approbation indépendante.',
                    )}
                  </Empty>
                )}
                <div className="section-heading">
                  <h3>{t('Processing attempts', 'Tentatives de traitement')}</h3>
                </div>
                {result.attempts?.length ? (
                  <div className="attempt-timeline">
                    {result.attempts.map((attempt, index) => (
                      <div key={attempt.id || index}>
                        <Clock3 size={17} />
                        <div>
                          <strong>
                            {t('Attempt', 'Tentative')} {index + 1}
                          </strong>
                          <p>
                            {date(attempt.started_at, locale)} · {attempt.status || '—'}
                          </p>
                          {attempt.error && <code>{attempt.error}</code>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted">
                    {t(
                      'No posting attempts recorded.',
                      'Aucune tentative de comptabilisation enregistrée.',
                    )}
                  </p>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </Dialog>
  )
}
function CalculationStep({
  number,
  title,
  value,
  note,
  final = false,
}: {
  number: string
  title: string
  value: string
  note: string
  final?: boolean
}) {
  return (
    <div className={`calculation-step ${final ? 'final-step' : ''}`}>
      <span className="step-number">{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{note}</p>
      </div>
      <span className="amount">{value}</span>
    </div>
  )
}
function account(code: string, t: (en: string, fr: string) => string) {
  const names: Record<string, string> = {
    '5100': t('Program expense', 'Charge du programme'),
    '2100': t('Program payable', 'Créditeurs du programme'),
    '1100': t('Simulated clearing', 'Compensation simulée'),
  }
  return `${code} · ${names[code] || code}`
}

export function ReconciliationPage({
  locale,
  revision,
  user,
  refresh,
  onTrace,
}: {
  locale: Locale
  revision: number
  user: User
  refresh: () => void
  onTrace: (id: string) => void
}) {
  const t = useText()
  const [query, setQuery] = useStoredState('reconciliation.query', '')
  const [classification, setClassification] = useStoredState('reconciliation.classification', '')
  const [page, setPage] = useStoredState('reconciliation.page', 1)
  const [file, setFile] = useState<File | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [disposition, setDisposition] = useState<Reconciliation | null>(null)
  const [reason, setReason] = useState('')
  const resource = useResource<Page<Reconciliation>>(
    `/reconciliation?q=${encodeURIComponent(query)}&classification=${classification}&page=${page}&page_size=15`,
    revision,
    true,
  )
  const upload = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    try {
      const body = new FormData()
      body.append('file', file)
      await api('/reconciliation', { method: 'POST', body })
      setShowImport(false)
      refresh()
      resource.refresh()
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  const accept = async (id: string) => {
    setBusy(true)
    try {
      await post(`/reconciliation/${id}/accept`)
      resource.refresh()
      refresh()
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  const saveDisposition = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await post(`/reconciliation/${disposition!.id}/disposition`, { reason })
      setDisposition(null)
      setReason('')
      resource.refresh()
      refresh()
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={t('MATCH WITH CONFIDENCE', 'RAPPROCHER AVEC CONFIANCE')}
        title={t('Settlement reconciliation', 'Rapprochement des règlements')}
        description={t(
          'See what matches. Understand what doesn’t. Keep every decision.',
          'Voyez ce qui correspond. Comprenez les écarts. Conservez chaque décision.',
        )}
      >
        <button
          className="button primary"
          disabled={user.role !== 'operator'}
          onClick={() => setShowImport(true)}
        >
          <Upload size={18} />
          {t('Import settlement', 'Importer un règlement')}
        </button>
      </PageHeading>
      <ErrorNotice error={error || resource.error} onDismiss={() => setError(null)} />
      <div className="info-callout reconciliation-note">
        <Info size={20} />
        <div>
          <strong>
            {t(
              'Only exact, authorized matches settle an obligation.',
              'Seules les correspondances exactes autorisées règlent une obligation.',
            )}
          </strong>
          <span>
            {t(
              'A review disposition records your investigation; it never turns a mismatched amount into a payment.',
              'Une décision d’examen consigne votre analyse; elle ne transforme jamais un montant différent en paiement.',
            )}
          </span>
        </div>
      </div>
      <div className="panel">
        <div className="table-toolbar">
          <SearchField
            value={query}
            onChange={(value) => {
              setQuery(value)
              setPage(1)
            }}
            label={t(
              'Search settlement or reference…',
              'Rechercher un règlement ou une référence…',
            )}
          />
          <label className="select-wrap">
            <ListFilter size={15} />
            <span className="sr-only">{t('Classification', 'Classement')}</span>
            <select
              value={classification}
              onChange={(event) => {
                setClassification(event.target.value)
                setPage(1)
              }}
            >
              <option value="">{t('All classifications', 'Tous les classements')}</option>
              <option value="MATCH">{t('Exact matches', 'Correspondances exactes')}</option>
              <option value="AMOUNT_MISMATCH">{t('Amount mismatches', 'Écarts de montant')}</option>
              <option value="DUPLICATE">{t('Duplicates', 'Doublons')}</option>
              <option value="MISSING">{t('Missing settlements', 'Règlements manquants')}</option>
              <option value="UNEXPECTED">
                {t('Unexpected references', 'Références inattendues')}
              </option>
            </select>
          </label>
        </div>
        {resource.loading ? (
          <Loading />
        ) : resource.data?.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('Reference', 'Référence')}</th>
                  <th>{t('Classification', 'Classement')}</th>
                  <th className="numeric">{t('Expected', 'Attendu')}</th>
                  <th className="numeric">{t('Received', 'Reçu')}</th>
                  <th>{t('Review', 'Examen')}</th>
                  <th>{t('Action', 'Action')}</th>
                </tr>
              </thead>
              <tbody>
                {resource.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.record_id ? (
                        <button className="text-link mono" onClick={() => onTrace(row.record_id!)}>
                          {row.reference}
                          <ArrowUpRight size={13} />
                        </button>
                      ) : (
                        <strong className="mono">{row.reference}</strong>
                      )}
                      <small className="table-subtext mono">
                        {row.settlement_reference || '—'}
                      </small>
                    </td>
                    <td>
                      <Status value={row.classification} />
                    </td>
                    <td className="numeric amount">{money(row.expected, locale)}</td>
                    <td
                      className={`numeric amount ${row.classification === 'AMOUNT_MISMATCH' ? 'warning-text' : ''}`}
                    >
                      {money(row.received, locale)}
                    </td>
                    <td>
                      {row.disposition ? (
                        <span className="disposition-text" title={row.disposition}>
                          {row.disposition}
                          <small>{row.actor}</small>
                        </span>
                      ) : (
                        <Status value={row.state || 'open'} />
                      )}
                    </td>
                    <td>
                      {row.classification === 'MATCH' ? (
                        <button
                          className="button small secondary"
                          disabled={
                            busy ||
                            user.role !== 'approver' ||
                            row.state === 'accepted' ||
                            row.accepted
                          }
                          onClick={() => void accept(row.id)}
                        >
                          <Check size={14} />
                          {row.state === 'accepted'
                            ? t('Accepted', 'Accepté')
                            : t('Accept', 'Accepter')}
                        </button>
                      ) : (
                        <button
                          className="text-link"
                          disabled={user.role !== 'approver'}
                          onClick={() => {
                            setDisposition(row)
                            setReason('')
                          }}
                        >
                          {t('Review', 'Examiner')}
                          <ArrowUpRight size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title={t('No settlement results', 'Aucun résultat de règlement')}>
            {t(
              'Import a synthetic settlement CSV to compare it against posted obligations.',
              'Importez un fichier CSV de règlements synthétiques pour le comparer aux obligations comptabilisées.',
            )}
          </Empty>
        )}
        <Pagination data={resource.data} onPage={setPage} />
      </div>
      {showImport && (
        <Dialog
          title={t('Import settlement file', 'Importer un fichier de règlements')}
          subtitle={t('SYNTHETIC SETTLEMENTS ONLY', 'RÈGLEMENTS SYNTHÉTIQUES UNIQUEMENT')}
          onClose={() => setShowImport(false)}
        >
          <form className="dialog-body" onSubmit={(event) => void upload(event)}>
            <ErrorNotice error={error} />
            <p className="lead-copy">
              {t(
                'The COBOL engine classifies exact matches, one-cent discrepancies, duplicates, missing and unexpected references.',
                'Le moteur COBOL classe les correspondances exactes, écarts d’un cent, doublons et références manquantes ou inattendues.',
              )}
            </p>
            <label className="dropzone">
              <Upload size={27} />
              <strong>
                {file?.name || t('Choose settlement CSV', 'Choisir le CSV de règlements')}
              </strong>
              <input
                type="file"
                accept=".csv"
                required
                aria-label={t('Settlement CSV file', 'Fichier CSV de règlements')}
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <code className="schema-line">settlement_reference,source,reference,amount</code>
            <div className="dialog-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setShowImport(false)}
              >
                {t('Cancel', 'Annuler')}
              </button>
              <button className="button primary" disabled={!file || busy}>
                {busy
                  ? t('Importing…', 'Importation…')
                  : t('Run reconciliation', 'Lancer le rapprochement')}
                <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {disposition && (
        <Dialog
          title={t('Record a review disposition', 'Consigner une décision d’examen')}
          subtitle={disposition.reference}
          onClose={() => setDisposition(null)}
        >
          <form className="dialog-body" onSubmit={(event) => void saveDisposition(event)}>
            <ErrorNotice error={error} />
            <Status value={disposition.classification} />
            <p className="lead-copy">
              {t(
                'Describe the investigation or next action. The source amount and exception remain preserved.',
                'Décrivez l’analyse ou la prochaine action. Le montant source et l’exception restent conservés.',
              )}
            </p>
            <label htmlFor="disposition-reason">
              {t('Reason for disposition', 'Motif de la décision')}
            </label>
            <textarea
              id="disposition-reason"
              required
              minLength={5}
              maxLength={2000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <div className="dialog-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setDisposition(null)}
              >
                {t('Cancel', 'Annuler')}
              </button>
              <button className="button primary" disabled={busy}>
                {t('Save review', 'Enregistrer l’examen')}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  )
}

export function Ledger({
  locale,
  revision,
  user,
  search,
  setSearch,
  refresh,
  onTrace,
}: {
  locale: Locale
  revision: number
  user: User
  search: string
  setSearch: (value: string) => void
  refresh: () => void
  onTrace: (id: string) => void
}) {
  const t = useText()
  const [page, setPage] = useStoredState('ledger.page', 1)
  const [tab, setTab] = useStoredState<'journals' | 'audit'>('ledger.tab', 'journals')
  const [reversing, setReversing] = useState<Journal | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const resource = useResource<Page<Journal>>(
    `/ledger?q=${encodeURIComponent(search)}&page=${page}&page_size=15`,
    revision,
    true,
  )
  const audit = useResource<Page<Audit>>(
    tab === 'audit' ? `/audit?page=${page}&page_size=15` : null,
    revision,
  )
  const verification = useResource<{ valid: boolean; count: number; head: string }>(
    tab === 'audit' ? '/audit/verify' : null,
    revision,
  )
  const reverse = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await post(`/ledger/${reversing!.id}/reverse`, { reason })
      setReversing(null)
      setReason('')
      resource.refresh()
      refresh()
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={t('A RECORD THAT ADDS UP', 'UN HISTORIQUE QUI S’ÉQUILIBRE')}
        title={t('General ledger', 'Grand livre')}
        description={t(
          'Balanced entries, preserved history and an ordered trail of accountability.',
          'Écritures équilibrées, historique conservé et piste ordonnée des responsabilités.',
        )}
      />
      <ErrorNotice
        error={error || resource.error || audit.error || verification.error}
        onDismiss={() => setError(null)}
      />
      <div className="page-tabs">
        <button
          className={tab === 'journals' ? 'active' : ''}
          onClick={() => {
            setTab('journals')
            setPage(1)
          }}
        >
          <LandmarkIcon />
          {t('Journal entries', 'Écritures comptables')}
        </button>
        <button
          className={tab === 'audit' ? 'active' : ''}
          onClick={() => {
            setTab('audit')
            setPage(1)
          }}
        >
          <History size={17} />
          {t('Audit timeline', 'Chronologie d’audit')}
        </button>
      </div>
      {tab === 'journals' ? (
        <div className="panel">
          <div className="table-toolbar">
            <SearchField
              value={search}
              onChange={(value) => {
                setSearch(value)
                setPage(1)
              }}
              label={t('Search a source reference…', 'Rechercher une référence source…')}
            />
            <span className="balanced-label">
              <ShieldCheck size={16} />
              {t('Double entry · CAD', 'Partie double · CAD')}
            </span>
          </div>
          {resource.loading ? (
            <Loading />
          ) : resource.data?.items.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t('Journal / reference', 'Écriture / référence')}</th>
                    <th>{t('Type', 'Type')}</th>
                    <th>{t('Debit → credit', 'Débit → crédit')}</th>
                    <th className="numeric">{t('Amount', 'Montant')}</th>
                    <th>{t('Posted', 'Comptabilisé')}</th>
                    <th>{t('Action', 'Action')}</th>
                  </tr>
                </thead>
                <tbody>
                  {resource.data.items.map((journal) => (
                    <tr key={journal.id}>
                      <td>
                        <button
                          className="text-link mono"
                          onClick={() => onTrace(journal.record_id)}
                        >
                          {journal.reference}
                          <ArrowUpRight size={13} />
                        </button>
                        <small className="table-subtext mono">{short(journal.id, 14)}</small>
                        {journal.reversal_of && (
                          <small className="table-subtext">
                            ↳ {t('Reversal of', 'Contrepassation de')} {short(journal.reversal_of)}
                          </small>
                        )}
                      </td>
                      <td>
                        <span className="journal-kind">
                          {journal.kind === 'obligation'
                            ? t('Obligation', 'Obligation')
                            : journal.kind === 'settlement'
                              ? t('Settlement', 'Règlement')
                              : journal.kind === 'reversal'
                                ? t('Reversal', 'Contrepassation')
                                : journal.kind}
                        </span>
                      </td>
                      <td>
                        <span className="account-pair mono">
                          {journal.debit}
                          <ArrowRight size={13} />
                          {journal.credit}
                        </span>
                      </td>
                      <td className="numeric amount">{money(journal.amount, locale)}</td>
                      <td className="muted nowrap">{date(journal.created_at, locale)}</td>
                      <td>
                        {journal.kind.toLowerCase() === 'obligation' && (
                          <button
                            className="icon-button"
                            disabled={user.role !== 'approver'}
                            aria-label={`${t('Reverse journal', 'Contrepasser l’écriture')} ${journal.reference}`}
                            title={t(
                              'Request an authorized reversal',
                              'Demander une contrepassation autorisée',
                            )}
                            onClick={() => {
                              setReversing(journal)
                              setReason('')
                            }}
                          >
                            <RotateCcw size={17} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title={t('No journals posted', 'Aucune écriture comptabilisée')}>
              {t(
                'Approve and post a calculated batch to create balanced obligations.',
                'Approuvez et comptabilisez un lot calculé pour créer des obligations équilibrées.',
              )}
            </Empty>
          )}
          <Pagination data={resource.data} onPage={setPage} />
        </div>
      ) : (
        <>
          <div className="audit-verification">
            <ShieldCheck size={24} />
            <div>
              <strong>
                {verification.data
                  ? verification.data.valid
                    ? t('Audit chain verified', 'Chaîne d’audit vérifiée')
                    : t('Audit chain verification failed', 'Échec de la vérification de la chaîne')
                  : t('Verifying audit chain…', 'Vérification de la chaîne…')}
              </strong>
              <p>
                {verification.data?.count || 0} {t('ordered events', 'événements ordonnés')} ·{' '}
                <code>{short(verification.data?.head, 32)}</code>
              </p>
            </div>
          </div>
          <Panel
            title={t('Consequential actions', 'Actions significatives')}
            subtitle={t(
              'Actor, action and time are retained in a serialized hash chain.',
              'L’acteur, l’action et l’heure sont conservés dans une chaîne de hachage sérialisée.',
            )}
          >
            {audit.data?.items.length ? (
              <div className="audit-list">
                {audit.data.items.map((event, index) => (
                  <div className="audit-event" key={event.id || index}>
                    <span className="audit-sequence">{event.id || index + 1}</span>
                    <div>
                      <strong>
                        <AuditAction action={event.action || 'EVENT'} />
                      </strong>
                      <p>
                        {event.actor} · {date(event.created_at, locale)}
                      </p>
                      {!!event.payload && (
                        <details>
                          <summary>{t('Event details', 'Détails de l’événement')}</summary>
                          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                    <ShieldCheck size={17} />
                  </div>
                ))}
              </div>
            ) : (
              <Empty />
            )}
            <Pagination data={audit.data} onPage={setPage} />
          </Panel>
          <div className="bottom-note">
            <Info size={17} />
            {t(
              'Tamper-evident within the local trust model. A privileged rewrite of the whole chain and its anchor is outside this protection.',
              'Détection d’altération dans le modèle de confiance local. La réécriture privilégiée de toute la chaîne et de son ancrage échappe à cette protection.',
            )}
          </div>
        </>
      )}
      {reversing && (
        <Dialog
          title={t('Create a compensating journal', 'Créer une écriture compensatrice')}
          subtitle={reversing.reference}
          onClose={() => setReversing(null)}
        >
          <form className="dialog-body" onSubmit={(event) => void reverse(event)}>
            <ErrorNotice error={error} />
            <p className="lead-copy">
              {t(
                'The original journal remains unchanged. Only an unsettled, unreversed obligation can be reversed. Already settled obligations are rejected.',
                'L’écriture d’origine reste inchangée. Seule une obligation non réglée et non contrepassée peut être annulée. Les obligations déjà réglées sont rejetées.',
              )}
            </p>
            <KeyValue label={t('Original obligation', 'Obligation d’origine')}>
              {money(reversing.amount, locale)}
            </KeyValue>
            <label htmlFor="reversal-reason">
              {t('Authorization reason', 'Motif d’autorisation')}
            </label>
            <textarea
              id="reversal-reason"
              required
              minLength={5}
              maxLength={2000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <div className="dialog-actions">
              <button type="button" className="button secondary" onClick={() => setReversing(null)}>
                {t('Cancel', 'Annuler')}
              </button>
              <button className="button primary" disabled={busy}>
                <RotateCcw size={16} />
                {t('Authorize reversal', 'Autoriser la contrepassation')}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  )
}
function LandmarkIcon() {
  return <FileStack size={17} />
}

export function Workbench({
  locale,
  revision,
  user,
  onBatch,
  onTrace,
}: {
  locale: Locale
  revision: number
  user: User
  onBatch: (id: string) => void
  onTrace: (id: string) => void
}) {
  const t = useText()
  const batches = useResource<Page<Batch>>('/batches?page=1&page_size=100', revision)
  const [selected, setSelected] = useStoredState('workbench.batch', '')
  const activeId =
    (batches.data?.items.some((item) => item.id === selected) ? selected : '') ||
    batches.data?.items.find((item) => item.result_digest)?.id ||
    ''
  const detail = useResource<Batch>(activeId ? `/batches/${activeId}` : null, revision)
  const benchmarks = useResource<{ reports: unknown[]; measured: boolean }>('/benchmarks', revision)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useResource<Job>(jobId ? `/jobs/${jobId}` : null, 0, true)
  const [error, setError] = useState<Error | null>(null)
  const [busy, setBusy] = useState(false)
  const run = async (kind: 'replay' | 'compare') => {
    setBusy(true)
    setError(null)
    try {
      const result = await post<Job>(`/batches/${activeId}/${kind}`)
      setJobId(result.id)
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={t('FOLLOW THE EVIDENCE', 'SUIVRE LES PREUVES')}
        title={t('Under the hood. In the open.', 'Sous le capot. En toute transparence.')}
        description={t(
          'Inspect the bytes, reproduce the calculation and take the evidence with you.',
          'Examinez les octets, reproduisez le calcul et emportez les preuves.',
        )}
      />
      <ErrorNotice error={error || batches.error || detail.error} />
      <div className="workbench-banner">
        <div className="workbench-symbol">
          <Braces size={40} />
        </div>
        <div>
          <span className="eyebrow">
            {t('NATIVE EXECUTION · EXACT DECIMALS', 'EXÉCUTION NATIVE · DÉCIMALES EXACTES')}
          </span>
          <h2>{t('The calculation belongs to COBOL.', 'Le calcul appartient à COBOL.')}</h2>
          <p>
            {t(
              'Validation, reimbursement rules, journal proposals and reconciliation run in the compiled engine. Every result can be traced to its inputs.',
              'La validation, les règles de remboursement, les écritures proposées et le rapprochement s’exécutent dans le moteur compilé. Chaque résultat est relié à ses entrées.',
            )}
          </p>
        </div>
        <span className="workbench-build mono">{short(detail.data?.engine_build, 20)}</span>
      </div>
      <div className="workbench-selector">
        <label htmlFor="workbench-batch">{t('Evidence context', 'Contexte des preuves')}</label>
        <select
          id="workbench-batch"
          value={activeId}
          onChange={(event) => {
            setSelected(event.target.value)
            setJobId(null)
          }}
        >
          {!batches.data?.items.length && (
            <option value="">{t('No calculated batches', 'Aucun lot calculé')}</option>
          )}
          {batches.data?.items
            .filter((item) => item.result_digest)
            .map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name} · {batch.policy}
              </option>
            ))}
        </select>
        <button className="text-link" disabled={!activeId} onClick={() => onBatch(activeId)}>
          {t('Open batch', 'Ouvrir le lot')}
          <ArrowUpRight size={15} />
        </button>
      </div>
      <div className="workbench-cards">
        <WorkbenchCard
          icon={<Fingerprint size={23} />}
          eyebrow="01 / TRACE"
          title={t('Original bytes. Explained.', 'Les octets d’origine, expliqués.')}
          description={t(
            'Inspect a source record, its copybook fields and every step of the engine’s calculation.',
            'Examinez un enregistrement source, ses champs de copybook et chaque étape du calcul.',
          )}
          action={t('Trace a payment', 'Suivre un paiement')}
          disabled={!detail.data?.records?.length}
          onClick={() => {
            const record =
              detail.data?.records?.find((row) => row.eligible_cost === '123.45') ||
              detail.data?.records?.[0]
            if (record) onTrace(record.id)
          }}
        />
        <WorkbenchCard
          icon={<RotateCcw size={23} />}
          eyebrow="02 / REPLAY"
          title={t('Reproduce the result.', 'Reproduire le résultat.')}
          description={t(
            'Re-execute the frozen input with its recorded policy and engine build. Compare canonical financial digests.',
            'Réexécutez l’entrée figée avec sa politique et sa version du moteur. Comparez les empreintes financières canoniques.',
          )}
          action={t('Run historical replay', 'Lancer le rejeu historique')}
          disabled={!activeId || busy}
          onClick={() => void run('replay')}
        />
        <WorkbenchCard
          icon={<GitCompareArrows size={23} />}
          eyebrow="03 / COMPARE"
          title={t('A policy. A different perspective.', 'Une politique. Une autre perspective.')}
          description={t(
            'Compare V1 at 75% with V2 at 80%, both capped at $2,500. Read-only analysis leaves approvals intact.',
            'Comparez V1 à 75 % avec V2 à 80 %, plafonnées à 2 500 $. L’analyse en lecture seule préserve les approbations.',
          )}
          action={t('Compare policy versions', 'Comparer les politiques')}
          disabled={!activeId || busy}
          onClick={() => void run('compare')}
        />
      </div>
      {jobId && <JobResult job={job.data} error={job.error} locale={locale} />}
      <div className="workbench-lower">
        <Panel
          title={t('Take the proof with you', 'Emportez les preuves')}
          subtitle={t(
            'A portable, reproducible evidence package.',
            'Un dossier de preuves portable et reproductible.',
          )}
        >
          <div className="evidence-content">
            <span className="evidence-icon">
              <ArrowDownToLine size={30} />
            </span>
            <div>
              <h3>{t('Evidence bundle', 'Dossier de preuves')}</h3>
              <p>
                {t(
                  'Original input, canonical results, engine identity, journals, control totals, exceptions and audit verification in one ZIP.',
                  'Entrée originale, résultats canoniques, identité du moteur, écritures, totaux de contrôle, exceptions et vérification d’audit dans un ZIP.',
                )}
              </p>
              {user.role === 'auditor' && activeId ? (
                <a href={`/api/batches/${activeId}/evidence`} className="button primary" download>
                  <Download size={16} />
                  {t('Export evidence', 'Exporter les preuves')}
                </a>
              ) : (
                <span className="hint">
                  <ShieldCheck size={15} />
                  {t(
                    'Sign in as an auditor to export evidence.',
                    'Connectez-vous en tant qu’auditeur pour exporter les preuves.',
                  )}
                </span>
              )}
            </div>
          </div>
        </Panel>
        <Panel
          title={t('Measured performance', 'Performance mesurée')}
          subtitle={t(
            'Executed reports, without extrapolation.',
            'Rapports exécutés, sans extrapolation.',
          )}
        >
          <div className="benchmark-content">
            {benchmarks.error ? (
              <p className="muted">
                {t(
                  'Benchmark reports are not available from this service.',
                  'Les rapports de performance ne sont pas disponibles auprès de ce service.',
                )}
              </p>
            ) : benchmarks.data?.measured && benchmarks.data.reports.length > 0 ? (
              <details>
                <summary>
                  {t(
                    'Inspect recorded benchmark reports',
                    'Examiner les rapports de performance conservés',
                  )}
                </summary>
                <pre>{JSON.stringify(benchmarks.data, null, 2)}</pre>
              </details>
            ) : (
              <>
                <Clock3 size={27} />
                <h3>
                  {t('No measurements published yet', 'Aucune mesure publiée pour le moment')}
                </h3>
                <p>
                  {t(
                    'Only actually executed engine and end-to-end benchmarks are shown here.',
                    'Seuls les essais du moteur et de bout en bout réellement exécutés sont affichés ici.',
                  )}
                </p>
              </>
            )}
          </div>
        </Panel>
      </div>
      <PackedInspector />
      <div className="bottom-note">
        <Info size={17} />
        {t(
          'This bounded legacy format is a demonstration, not a general mainframe compatibility claim.',
          'Ce format historique délimité est une démonstration, sans prétention de compatibilité générale avec les ordinateurs centraux.',
        )}
      </div>
    </>
  )
}
function WorkbenchCard({
  icon,
  eyebrow,
  title,
  description,
  action,
  onClick,
  disabled,
}: {
  icon: React.ReactNode
  eyebrow: string
  title: string
  description: string
  action: string
  onClick: () => void
  disabled: boolean
}) {
  return (
    <section className="workbench-card">
      <div>
        <span className="workbench-card-icon">{icon}</span>
        <span className="mono">{eyebrow}</span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      <button className="text-link" onClick={onClick} disabled={disabled}>
        {action}
        <ArrowRight size={16} />
      </button>
    </section>
  )
}

function PackedInspector() {
  const t = useText()
  const resource = useResource<{
    cases: { name: string; raw_hex: string; valid: boolean; decoded?: string; error?: string }[]
  }>('/engine/packed')
  const [selected, setSelected] = useState(0)
  const item = resource.data?.cases[selected]
  return (
    <Panel
      title={t('A closer look at packed decimal', 'Regard sur le décimal condensé')}
      subtitle={t(
        'Bounded IBM-037 character fields + signed COMP-3. Validated by the compiled engine.',
        'Champs de caractères IBM-037 délimités + COMP-3 signé. Validés par le moteur compilé.',
      )}
      className="packed-panel"
    >
      <div className="packed-content">
        <ErrorNotice error={resource.error} />
        {!resource.data ? (
          <Loading />
        ) : (
          <>
            <div className="packed-options">
              {resource.data.cases.map((entry, index) => (
                <button
                  className={index === selected ? 'selected' : ''}
                  key={entry.name}
                  onClick={() => setSelected(index)}
                >
                  <FileCode2 size={17} />
                  <span className="mono">{entry.name}</span>
                  <span className={`status ${entry.valid ? 'success' : 'danger'}`}>
                    {entry.valid
                      ? t('Valid representation', 'Représentation valide')
                      : t('Corruption rejected', 'Corruption rejetée')}
                  </span>
                </button>
              ))}
            </div>
            {item && (
              <>
                <div className="packed-detail">
                  <div>
                    <span className="eyebrow">PIC S9(7)V99 COMP-3</span>
                    <h3>
                      {t(
                        'Five bytes. Nine digits. One sign.',
                        'Cinq octets. Neuf chiffres. Un signe.',
                      )}
                    </h3>
                    <p>
                      {t(
                        'Original first-detail bytes 40–44. Positive signs A/C/E/F and negative signs B/D are supported. Every digit nibble is checked before calculation.',
                        'Octets originaux 40–44 du premier détail. Signes positifs A/C/E/F et négatifs B/D acceptés. Chaque quartet numérique est vérifié avant le calcul.',
                      )}
                    </p>
                  </div>
                  <div
                    className={`nibble-row ${item.valid ? '' : 'invalid'}`}
                    aria-label={t(
                      'Packed decimal hexadecimal nibbles',
                      'Quartets hexadécimaux du décimal condensé',
                    )}
                  >
                    {item.raw_hex
                      .slice(242, 252)
                      .toUpperCase()
                      .split('')
                      .map((digit, index) => (
                        <span key={index} className={index === 9 ? 'sign-nibble' : ''}>
                          {digit}
                        </span>
                      ))}
                  </div>
                </div>
                {!item.valid && (
                  <div className="packed-finding">
                    <Info size={17} />
                    <span>
                      <strong>{t('Engine rejection', 'Rejet du moteur')}</strong> ·{' '}
                      <Reason code={item.error?.split(':')[0] || 'PACKED_DIGIT'} />
                      <code>{item.error}</code>
                    </span>
                  </div>
                )}
                <details>
                  <summary>
                    {t(
                      'Inspect original file bytes and decoded fields',
                      'Examiner les octets originaux et les champs décodés',
                    )}
                  </summary>
                  <KeyValue
                    label={t('Original bytes — hexadecimal', 'Octets originaux — hexadécimal')}
                    mono
                  >
                    {item.raw_hex}
                  </KeyValue>
                  {item.decoded && (
                    <>
                      <p className="hint">
                        {t(
                          'Character fields are decoded individually. Packed bytes are validated independently in COBOL.',
                          'Les champs de caractères sont décodés individuellement. Les octets condensés sont validés séparément en COBOL.',
                        )}
                      </p>
                      <pre>{item.decoded}</pre>
                    </>
                  )}
                </details>
                <a href={`/api/fixtures/${item.name}`} className="text-link" download>
                  <Download size={14} />
                  {t('Download this fixture', 'Télécharger cet exemple')}
                </a>
              </>
            )}
          </>
        )}
      </div>
    </Panel>
  )
}
