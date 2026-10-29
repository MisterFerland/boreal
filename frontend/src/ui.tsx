import { createContext, useContext, useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileStack,
  Globe2,
  LoaderCircle,
  X,
} from 'lucide-react'
import type { Locale, Page } from './types'
import { ApiError } from './api'
import { messages, actions } from './messages'

export const LocaleContext = createContext<Locale>('en-CA')
export const LocaleSwitchContext = createContext<() => void>(() => {})
export function useText() {
  const locale = useContext(LocaleContext)
  return (en: string, fr: string) => (locale === 'fr-CA' ? fr : en)
}
export function Mark({ small = false }: { small?: boolean }) {
  return (
    <svg
      className={small ? 'mark small' : 'mark'}
      width="36"
      height="39"
      viewBox="0 0 36 39"
      aria-hidden="true"
    >
      <path d="M18 1 34 32H23L18 21 13 32H2L18 1Z" fill="currentColor" />
      <path d="m18 29 5 9H13l5-9Z" fill="currentColor" opacity=".5" />
    </svg>
  )
}
export function Status({ value }: { value: string | undefined }) {
  const t = useText()
  const status = value || 'unknown'
  const labels: Record<string, [string, string]> = {
    rejected: ['Rejected', 'Rejeté'],
    abandoned: ['Abandoned claim', 'Attribution abandonnée'],
    queued: ['Queued', 'En attente'],
    calculating: ['Calculating', 'Calcul en cours'],
    review: ['Ready for review', 'À examiner'],
    approved: ['Approved', 'Approuvé'],
    posting: ['Posting', 'Comptabilisation'],
    posted: ['Posted', 'Comptabilisé'],
    quarantined: ['Quarantined', 'En quarantaine'],
    failed: ['Failed', 'Échec'],
    retry: ['Recovery pending', 'Reprise en attente'],
    running: ['Running', 'En cours'],
    succeeded: ['Completed', 'Terminé'],
    ACCEPTED: ['Accepted', 'Accepté'],
    MATCH: ['Exact match', 'Correspondance exacte'],
    AMOUNT_MISMATCH: ['Amount mismatch', 'Écart de montant'],
    DUPLICATE: ['Duplicate', 'Doublon'],
    MISSING: ['Missing settlement', 'Règlement manquant'],
    UNEXPECTED: ['Unexpected reference', 'Référence inattendue'],
    settled: ['Settled', 'Réglé'],
    reversed: ['Reversed', 'Contrepassé'],
    open: ['Open', 'Ouvert'],
    accepted: ['Accepted', 'Accepté'],
    reviewed: ['Reviewed', 'Examiné'],
    unknown: ['Unavailable', 'Indisponible'],
  }
  const label = labels[status]
  const tone = [
    'approved',
    'posted',
    'succeeded',
    'ACCEPTED',
    'MATCH',
    'accepted',
    'settled',
  ].includes(status)
    ? 'success'
    : ['failed', 'rejected', 'quarantined', 'AMOUNT_MISMATCH', 'DUPLICATE', 'UNEXPECTED'].includes(
          status,
        )
      ? 'danger'
      : ['review', 'retry', 'MISSING', 'open'].includes(status)
        ? 'warning'
        : 'neutral'
  return (
    <span className={`status ${tone}`}>
      <span className="status-dot" />
      {label ? t(...label) : status.replaceAll('_', ' ')}
    </span>
  )
}
export function Reason({ code }: { code: string }) {
  const t = useText()
  return <>{messages[code] ? t(...messages[code]) : code}</>
}
export function AuditAction({ action }: { action: string }) {
  const t = useText()
  return <>{actions[action] ? t(...actions[action]) : action}</>
}
export function JobKind({ kind }: { kind: string }) {
  const t = useText()
  const names: Record<string, [string, string]> = {
    calculate: ['Calculation', 'Calcul'],
    post: ['Posting', 'Comptabilisation'],
    reconcile: ['Reconciliation', 'Rapprochement'],
    replay: ['Replay', 'Rejeu'],
    compare: ['Policy comparison', 'Comparaison des politiques'],
  }
  return <>{names[kind] ? t(...names[kind]) : kind}</>
}
export function Empty({ title, children }: { title?: string; children?: ReactNode }) {
  const t = useText()
  return (
    <div className="empty">
      <span className="empty-icon">
        <FileStack size={25} />
      </span>
      <h3>{title || t('Nothing here yet', 'Aucun résultat pour le moment')}</h3>
      <p>
        {children ||
          t(
            'Records will appear here once a batch has been processed.',
            'Les enregistrements apparaîtront ici après le traitement d’un lot.',
          )}
      </p>
    </div>
  )
}
export function Loading() {
  const t = useText()
  return (
    <div className="loading" role="status">
      <LoaderCircle size={20} className="spin" />
      {t('Loading your workspace…', 'Chargement de votre espace…')}
    </div>
  )
}
export function ErrorNotice({
  error,
  onDismiss,
}: {
  error: Error | string | null
  onDismiss?: () => void
}) {
  const t = useText()
  if (!error) return null
  return (
    <div className="error-notice" role="alert">
      <CircleAlert size={19} />
      <div>
        <strong>
          {t('The request could not be completed.', 'La demande n’a pas pu être exécutée.')}
        </strong>
        <p>
          {error instanceof ApiError ? (
            <>
              <code>{error.code}</code> ·{' '}
              {messages[error.code]
                ? t(...messages[error.code])
                : t(
                    error.message,
                    'Le service a signalé une erreur. Consultez le code de diagnostic.',
                  )}
            </>
          ) : (
            t(
              'The service connection was interrupted. Try again.',
              'La connexion au service a été interrompue. Réessayez.',
            )
          )}
        </p>
      </div>
      {onDismiss && (
        <button
          className="icon-button"
          onClick={onDismiss}
          aria-label={t('Dismiss error', 'Fermer l’erreur')}
        >
          <X size={17} />
        </button>
      )}
    </div>
  )
}
export function Dialog({
  title,
  subtitle,
  children,
  onClose,
  drawer = false,
  suspended = false,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  onClose: () => void
  drawer?: boolean
  suspended?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const t = useText()
  const switchLocale = useContext(LocaleSwitchContext)
  useEffect(() => {
    const node = ref.current
    const previous = document.activeElement as HTMLElement
    node?.showModal()
    return () => {
      node?.close()
      previous?.focus()
    }
  }, [])
  return (
    <dialog
      ref={ref}
      className={drawer ? 'dialog drawer' : 'dialog'}
      aria-labelledby={titleId}
      aria-hidden={suspended ? true : undefined}
      inert={suspended}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="dialog-inner">
        <header className="dialog-header">
          <div>
            {subtitle && <span className="eyebrow">{subtitle}</span>}
            <h2 id={titleId}>{title}</h2>
          </div>
          <div className="dialog-header-actions">
            <button
              className="language-button"
              type="button"
              onClick={switchLocale}
              aria-label={t('Passer le dialogue en français', 'Switch dialog to English')}
            >
              <Globe2 size={15} />
              {t('FR', 'EN')}
            </button>
            <button
              className="icon-button close-dialog"
              onClick={onClose}
              aria-label={t('Close dialog', 'Fermer la fenêtre')}
            >
              <X size={21} />
            </button>
          </div>
        </header>
        {children}
      </div>
    </dialog>
  )
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = '',
}: {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}
export function Pagination<T>({
  data,
  onPage,
}: {
  data: Page<T> | null
  onPage: (page: number) => void
}) {
  const t = useText()
  if (!data || !data.total) return null
  return (
    <div className="pagination">
      <span>
        {t('Showing', 'Affichage')} {(data.page - 1) * data.page_size + 1}–
        {Math.min(data.page * data.page_size, data.total)} {t('of', 'sur')} {data.total}
      </span>
      <div>
        <button
          className="icon-button"
          disabled={data.page <= 1}
          onClick={() => onPage(data.page - 1)}
          aria-label={t('Previous page', 'Page précédente')}
        >
          <ChevronLeft size={18} />
        </button>
        <span>{data.page}</span>
        <button
          className="icon-button"
          disabled={data.page * data.page_size >= data.total}
          onClick={() => onPage(data.page + 1)}
          aria-label={t('Next page', 'Page suivante')}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  )
}
export function TextLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  )
}
export function KeyValue({
  label,
  children,
  mono = false,
}: {
  label: string
  children: ReactNode
  mono?: boolean
}) {
  return (
    <div className="key-value">
      <span>{label}</span>
      <div className={mono ? 'mono break' : ''}>{children || '—'}</div>
    </div>
  )
}
