import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Braces,
  Check,
  CheckCheck,
  Download,
  FileStack,
  Fingerprint,
  Gauge,
  Globe2,
  Landmark,
  LogOut,
  Menu,
  Moon,
  Plus,
  Search,
  ShieldCheck,
  Sun,
  Upload,
  Workflow,
} from 'lucide-react'
import type { FormEvent } from 'react'
import { ApiError, api, post, setCsrf } from './api'
import type { Batch, Locale, Overview, Session, View } from './types'
import { date, money, short } from './format'
import {
  AuditAction,
  Dialog,
  Empty,
  ErrorNotice,
  Loading,
  LocaleContext,
  LocaleSwitchContext,
  Mark,
  Panel,
  Status,
  TextLink,
  useText,
} from './ui'
import { useResource, useStoredState } from './hooks'
import { BatchDetail, Batches, Ledger, ReconciliationPage, TraceDrawer, Workbench } from './pages'

const navItems = [
  { id: 'overview' as View, en: 'Overview', fr: 'Vue d’ensemble', icon: Gauge },
  { id: 'batches' as View, en: 'Batches', fr: 'Lots', icon: FileStack },
  { id: 'reconciliation' as View, en: 'Reconciliation', fr: 'Rapprochement', icon: CheckCheck },
  { id: 'ledger' as View, en: 'Ledger', fr: 'Grand livre', icon: Landmark },
  { id: 'workbench' as View, en: 'Workbench', fr: 'Atelier', icon: Braces },
]
function stored(key: string, fallback: string) {
  try {
    return localStorage.getItem(`boreal.v1.${key}`) || fallback
  } catch {
    return fallback
  }
}

export default function App() {
  const [locale, setLocale] = useState<Locale>(() =>
    stored('locale', 'en-CA') === 'fr-CA' ? 'fr-CA' : 'en-CA',
  )
  const [theme, setTheme] = useState(() => stored('theme', 'light'))
  useEffect(() => {
    document.documentElement.lang = locale
    localStorage.setItem('boreal.v1.locale', locale)
  }, [locale])
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('boreal.v1.theme', theme)
  }, [theme])
  return (
    <LocaleContext value={locale}>
      <LocaleSwitchContext
        value={() => setLocale((value) => (value === 'en-CA' ? 'fr-CA' : 'en-CA'))}
      >
        <Console locale={locale} theme={theme} setLocale={setLocale} setTheme={setTheme} />
      </LocaleSwitchContext>
    </LocaleContext>
  )
}

function Console({
  locale,
  theme,
  setLocale,
  setTheme,
}: {
  locale: Locale
  theme: string
  setLocale: (l: Locale) => void
  setTheme: (t: string) => void
}) {
  const t = useText()
  const [session, setSession] = useState<Session | null>(null)
  const [checking, setChecking] = useState(true)
  const [view, setView] = useState<View>(() => {
    const saved = stored('view', 'overview')
    return navItems.some((n) => n.id === saved) ? (saved as View) : 'overview'
  })
  const [search, setSearch] = useStoredState('reference-search', '')
  const [palette, setPalette] = useState(false)
  const [upload, setUpload] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [traceId, setTraceId] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState<Error | null>(null)
  const overview = useResource<Overview>(session ? '/overview' : null, revision, true)
  const refresh = () => setRevision((value) => value + 1)
  useEffect(() => {
    api<Session>('/auth/me')
      .then((value) => {
        setCsrf(value.csrf)
        setSession(value)
      })
      .catch(() => {})
      .finally(() => setChecking(false))
  }, [])
  useEffect(() => {
    localStorage.setItem('boreal.v1.view', view)
    setMobile(false)
  }, [view])
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        setPalette((value) => !value)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(''), 7000)
    return () => clearTimeout(timer)
  }, [notice])
  const switchLanguage = () => setLocale(locale === 'en-CA' ? 'fr-CA' : 'en-CA')
  const signOut = async () => {
    try {
      await post('/auth/logout')
      setCsrf('')
      setSession(null)
      setBatchId(null)
      setTraceId(null)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        setCsrf('')
        setSession(null)
        setBatchId(null)
        setTraceId(null)
      } else {
        setError(cause as Error)
      }
    }
  }
  const currentNav = navItems.find((item) => item.id === view)!
  if (checking)
    return (
      <div className="splash">
        <Mark />
        <Loading />
      </div>
    )
  if (!session)
    return (
      <Login
        locale={locale}
        theme={theme}
        switchLanguage={switchLanguage}
        switchTheme={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        onLogin={(value) => {
          setCsrf(value.csrf)
          setSession(value)
          refresh()
        }}
      />
    )
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        {t('Skip to content', 'Aller au contenu')}
      </a>
      {mobile && (
        <button
          className="sidebar-scrim"
          aria-label={t('Close navigation', 'Fermer la navigation')}
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        className={`sidebar ${mobile ? 'is-open' : ''}`}
        aria-label={t('Main navigation', 'Navigation principale')}
      >
        <a
          href="#overview"
          className="brand"
          onClick={(event) => {
            event.preventDefault()
            setView('overview')
          }}
        >
          <Mark />
          <span>
            BOREAL<small>{t('FINANCIAL OPERATIONS', 'OPÉRATIONS FINANCIÈRES')}</small>
          </span>
        </a>
        <div className="workspace-select">
          <span className="workspace-icon">
            <Boxes size={18} />
          </span>
          <div>
            <strong>{t('Demonstration workspace', 'Espace de démonstration')}</strong>
            <small>{t('Local environment', 'Environnement local')}</small>
          </div>
          <span className="local-dot" />
        </div>
        <div className="nav-label">{t('WORKSPACE', 'ESPACE DE TRAVAIL')}</div>
        <nav>
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
              aria-current={view === item.id ? 'page' : undefined}
            >
              <item.icon size={19} />
              <span>{t(item.en, item.fr)}</span>
              {item.id === 'reconciliation' && !!overview.data?.metrics.exceptions && (
                <span className="nav-count">{overview.data.metrics.exceptions}</span>
              )}
              {view === item.id && <span className="nav-active-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="engine-card">
            <span className="eyebrow">
              <span className="status-dot" />
              {t('NATIVE COBOL ENGINE', 'MOTEUR COBOL NATIF')}
            </span>
            <strong>
              {overview.data ? short(overview.data.health.engine_build, 17) : 'GnuCOBOL'}
            </strong>
            <span>
              {t('Exact arithmetic. Traceable outcomes.', 'Calcul exact. Résultats traçables.')}
            </span>
            <button onClick={() => setView('workbench')}>
              {t('Explore the engine', 'Explorer le moteur')}
              <ArrowUpRight size={14} />
            </button>
          </div>
          <div className="sidebar-footer">
            <ShieldCheck size={15} />
            <span>{t('Synthetic data only', 'Données synthétiques uniquement')}</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-toggle"
              aria-label={t('Open navigation', 'Ouvrir la navigation')}
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span>{t('Workspace', 'Espace de travail')}</span>
            <span className="slash">/</span>
            <strong>{t(currentNav.en, currentNav.fr)}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="search-trigger"
              onClick={() => setPalette(true)}
              aria-label={t(
                'Search commands and references',
                'Rechercher les commandes et références',
              )}
            >
              <Search size={16} />
              <span>{t('Search anything…', 'Tout rechercher…')}</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              className="language-button"
              onClick={switchLanguage}
              aria-label={t('Passer en français', 'Switch to English')}
            >
              <Globe2 size={16} />
              {locale === 'en-CA' ? 'EN' : 'FR'}
            </button>
            <button
              className="icon-button"
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              aria-label={t(
                theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme',
                theme === 'light' ? 'Activer le thème sombre' : 'Activer le thème clair',
              )}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <div className="user-separator" />
            <span className="avatar" aria-hidden="true">
              {session.user.username.slice(0, 2).toUpperCase()}
            </span>
            <div className="user-info">
              <strong>{session.user.username}</strong>
              <span>
                {t(
                  session.user.role,
                  { operator: 'Opérateur', approver: 'Approbateur', auditor: 'Auditeur' }[
                    session.user.role
                  ],
                )}
              </span>
            </div>
            <button
              className="icon-button"
              onClick={() => void signOut()}
              aria-label={t('Sign out', 'Se déconnecter')}
              title={t('Sign out', 'Se déconnecter')}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <ErrorNotice error={error || overview.error} onDismiss={() => setError(null)} />
          {view === 'overview' && (
            <OverviewPage
              overview={overview.data}
              locale={locale}
              onView={setView}
              onBatch={setBatchId}
              onImport={() => setUpload(true)}
              canImport={session.user.role === 'operator'}
            />
          )}
          {view === 'batches' && (
            <Batches
              locale={locale}
              revision={revision}
              search={search}
              setSearch={setSearch}
              onBatch={setBatchId}
              onImport={() => setUpload(true)}
              canImport={session.user.role === 'operator'}
            />
          )}
          {view === 'reconciliation' && (
            <ReconciliationPage
              locale={locale}
              revision={revision}
              user={session.user}
              refresh={refresh}
              onTrace={setTraceId}
            />
          )}
          {view === 'ledger' && (
            <Ledger
              locale={locale}
              revision={revision}
              user={session.user}
              search={search}
              setSearch={setSearch}
              refresh={refresh}
              onTrace={setTraceId}
            />
          )}
          {view === 'workbench' && (
            <Workbench
              locale={locale}
              revision={revision}
              user={session.user}
              onBatch={setBatchId}
              onTrace={setTraceId}
            />
          )}
        </main>
        <footer className="page-footer">
          <span>
            <Mark small />
            BOREAL <span className="footer-dot">·</span>{' '}
            {t(
              'Independent portfolio demonstrator · Synthetic data',
              'Démonstrateur de portfolio indépendant · Données synthétiques',
            )}
          </span>
          <span>
            Yves Ferland <span className="footer-dot">/</span>{' '}
            {t('Built for scrutiny.', 'Conçu pour être vérifié.')}
          </span>
        </footer>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {palette && (
        <CommandPalette
          onClose={() => setPalette(false)}
          onView={(value) => {
            setView(value)
            setPalette(false)
          }}
          onSearch={(value) => {
            setSearch(value)
            setView('batches')
            setPalette(false)
          }}
          onImport={() => {
            setPalette(false)
            setUpload(true)
          }}
          canImport={session.user.role === 'operator'}
        />
      )}
      {upload && (
        <UploadDialog
          onClose={() => setUpload(false)}
          onSuccess={(batch) => {
            setUpload(false)
            refresh()
            setView('batches')
            setBatchId(batch.id)
            setNotice(
              t(
                'Batch received. The worker is validating the original file.',
                'Lot reçu. Le processus valide le fichier original.',
              ),
            )
          }}
        />
      )}
      {batchId && (
        <BatchDetail
          id={batchId}
          locale={locale}
          user={session.user}
          demo={!!overview.data?.health.demo}
          suspended={!!traceId}
          onClose={() => setBatchId(null)}
          onTrace={setTraceId}
          refresh={refresh}
        />
      )}
      {traceId && <TraceDrawer id={traceId} locale={locale} onClose={() => setTraceId(null)} />}
    </div>
  )
}

function Login({
  locale,
  theme,
  switchLanguage,
  switchTheme,
  onLogin,
}: {
  locale: Locale
  theme: string
  switchLanguage: () => void
  switchTheme: () => void
  onLogin: (value: Session) => void
}) {
  const t = useText()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onLogin(await post<Session>('/auth/login', { username, password }))
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <div className="brand">
          <Mark />
          <span>
            BOREAL<small>{t('FINANCIAL OPERATIONS', 'OPÉRATIONS FINANCIÈRES')}</small>
          </span>
        </div>
        <div className="login-story-content">
          <span className="eyebrow">
            {t('LEGACY PRECISION. MODERN PERSPECTIVE.', 'PRÉCISION ÉPROUVÉE. PERSPECTIVE MODERNE.')}
          </span>
          <h1>
            {t('Every transaction.', 'Chaque transaction.')}
            <br />
            <em>{t('Accounted for.', 'Expliquée.')}</em>
          </h1>
          <p>
            {t(
              'From original bytes to balanced books. A transparent workspace for reliable financial operations.',
              'Des octets d’origine aux écritures équilibrées. Un espace transparent pour des opérations financières fiables.',
            )}
          </p>
          <div className="login-flow">
            <span>
              <FileStack size={22} />
              {t('Import', 'Importer')}
            </span>
            <ArrowRight size={17} />
            <span>
              <Fingerprint size={22} />
              {t('Inspect', 'Examiner')}
            </span>
            <ArrowRight size={17} />
            <span>
              <ShieldCheck size={22} />
              {t('Approve', 'Approuver')}
            </span>
          </div>
        </div>
        <div className="login-story-footer">
          {t(
            'Independent portfolio demonstrator · Synthetic data',
            'Démonstrateur de portfolio indépendant · Données synthétiques',
          )}
          <span>Yves Ferland</span>
        </div>
        <div className="contour contour-one" />
        <div className="contour contour-two" />
        <div className="contour contour-three" />
      </section>
      <section className="login-form-side">
        <div className="login-controls">
          <button className="language-button" onClick={switchLanguage}>
            <Globe2 size={17} />
            {locale === 'en-CA' ? 'Français' : 'English'}
          </button>
          <button
            className="icon-button"
            onClick={switchTheme}
            aria-label={t('Change theme', 'Changer le thème')}
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </div>
        <form className="login-form" onSubmit={(event) => void submit(event)}>
          <span className="environment-tag">
            <span className="status-dot" />
            {t('LOCAL WORKSPACE', 'ESPACE LOCAL')}
          </span>
          <h2>{t('Welcome to BOREAL', 'Bienvenue dans BOREAL')}</h2>
          <p>
            {t(
              'Sign in to your operations workspace.',
              'Connectez-vous à votre espace de travail.',
            )}
          </p>
          <ErrorNotice error={error} />
          <label htmlFor="username">{t('Username', 'Nom d’utilisateur')}</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder={t('Your local account', 'Votre compte local')}
          />
          <label htmlFor="password">{t('Password', 'Mot de passe')}</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button className="button primary login-submit" disabled={busy}>
            {busy ? t('Signing in…', 'Connexion…') : t('Enter workspace', 'Accéder à l’espace')}
            <ArrowRight size={18} />
          </button>
          <div className="login-help">
            <ShieldCheck size={20} />
            <p>
              {t(
                'Use the credentials created by your local bootstrap. Operator, approver and auditor accounts have separate responsibilities.',
                'Utilisez les identifiants créés au démarrage local. Les comptes opérateur, approbateur et auditeur ont des responsabilités distinctes.',
              )}
            </p>
          </div>
        </form>
        <div className="login-bottom">
          <span>GnuCOBOL</span>
          <span>PostgreSQL</span>
          <span>{t('Exact decimal arithmetic', 'Arithmétique décimale exacte')}</span>
        </div>
      </section>
    </div>
  )
}

function OverviewPage({
  overview,
  locale,
  onView,
  onBatch,
  onImport,
  canImport,
}: {
  overview: Overview | null
  locale: Locale
  onView: (view: View) => void
  onBatch: (id: string) => void
  onImport: () => void
  canImport: boolean
}) {
  const t = useText()
  if (!overview) return <Loading />
  const { metrics, health } = overview
  const engineOk =
    health.engine === true ||
    ['ready', 'healthy', 'available', 'ok'].includes(String(health.engine).toLowerCase())
  const workerOk =
    health.worker === true ||
    ['ready', 'healthy', 'available', 'online', 'ok'].includes(String(health.worker).toLowerCase())
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow heading-eyebrow">
            {t('YOUR OPERATIONS, AT A GLANCE', 'VOS OPÉRATIONS EN UN COUP D’ŒIL')}
          </div>
          <h1>
            {t('Clear books. Confident decisions.', 'Des comptes clairs. Des décisions sûres.')}
          </h1>
          <p>
            {t(
              'A complete view of your reimbursement operations.',
              'Une vue complète de vos opérations de remboursement.',
            )}
          </p>
        </div>
        <button
          className="button primary"
          onClick={onImport}
          disabled={!canImport}
          title={!canImport ? t('Operator account required', 'Compte opérateur requis') : undefined}
        >
          <Plus size={18} />
          {t('Import batch', 'Importer un lot')}
        </button>
      </div>
      <div className="context-strip">
        <div>
          <span className="context-icon">
            <Workflow size={18} />
          </span>
          <strong>
            {t(
              'Community Infrastructure Reimbursement',
              'Remboursement des infrastructures communautaires',
            )}
          </strong>
          <span className="policy-pill">CIR · V1</span>
        </div>
        <span className="context-note">
          {t('Fictional policy', 'Politique fictive')}
          <span>·</span>CAD
        </span>
      </div>
      <div className="metric-grid">
        <Metric
          label={t('Approved obligations', 'Obligations approuvées')}
          value={money(metrics.approved, locale)}
          note={t('Authorized for posting', 'Autorisées à comptabiliser')}
          icon={<ShieldCheck size={18} />}
          onClick={() => onView('batches')}
        />
        <Metric
          label={t('Outstanding payable', 'Solde payable')}
          value={money(metrics.outstanding, locale)}
          note={t('Posted, awaiting settlement', 'Comptabilisé, en attente de règlement')}
          icon={<Landmark size={18} />}
          onClick={() => onView('ledger')}
        />
        <Metric
          label={t('Reconciliation exceptions', 'Exceptions de rapprochement')}
          value={String(metrics.exceptions)}
          note={t('Require a closer look', 'Nécessitent un examen')}
          icon={<CheckCheck size={18} />}
          onClick={() => onView('reconciliation')}
          attention={metrics.exceptions > 0}
        />
        <Metric
          label={t('Imported batches', 'Lots importés')}
          value={String(metrics.batches)}
          note={t('Preserved original source files', 'Fichiers sources originaux conservés')}
          icon={<FileStack size={18} />}
          onClick={() => onView('batches')}
        />
      </div>
      <div className="overview-grid">
        <Panel
          title={t('Recent batches', 'Lots récents')}
          subtitle={t(
            'From source file to approved payment.',
            'Du fichier source au paiement approuvé.',
          )}
          action={
            <TextLink onClick={() => onView('batches')}>
              {t('View all batches', 'Voir tous les lots')}
            </TextLink>
          }
          className="recent-panel"
        >
          {overview.recent_batches.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t('Batch / source', 'Lot / source')}</th>
                    <th>{t('Status', 'État')}</th>
                    <th className="numeric">{t('Payable', 'À payer')}</th>
                    <th className="table-action">
                      <span className="sr-only">{t('Open', 'Ouvrir')}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {overview.recent_batches.slice(0, 6).map((batch) => (
                    <tr key={batch.id}>
                      <td>
                        <button className="record-link" onClick={() => onBatch(batch.id)}>
                          <span className="file-tile">
                            <FileStack size={17} />
                          </span>
                          <span>
                            <strong>{batch.name}</strong>
                            <small>
                              {date(batch.created_at, locale)}
                              <span> · </span>
                              {batch.record_count || 0} {t('records', 'enregistrements')}
                            </small>
                          </span>
                        </button>
                      </td>
                      <td>
                        <Status value={batch.status} />
                      </td>
                      <td className="numeric amount">{money(batch.payable_total, locale)}</td>
                      <td>
                        <button
                          className="icon-button"
                          onClick={() => onBatch(batch.id)}
                          aria-label={`${t('Open batch', 'Ouvrir le lot')} ${batch.name}`}
                        >
                          <ArrowUpRight size={17} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title={t('The path to settlement', 'Parcours du règlement')}
          subtitle={t(
            'Distinct stages. One clear audit trail.',
            'Des étapes distinctes. Une piste claire.',
          )}
          className="lifecycle-panel"
        >
          <div className="lifecycle">
            {[
              {
                number: '01',
                label: t('Calculated', 'Calculé'),
                desc: t('Validated by the COBOL engine', 'Validé par le moteur COBOL'),
                amount: metrics.calculated,
              },
              {
                number: '02',
                label: t('Approved', 'Approuvé'),
                desc: t('Authorized by a separate approver', 'Autorisé par un autre approbateur'),
                amount: metrics.approved,
              },
              {
                number: '03',
                label: t('Posted', 'Comptabilisé'),
                desc: t('Committed to the general ledger', 'Inscrit au grand livre'),
                amount: metrics.posted,
              },
              {
                number: '04',
                label: t('Settled', 'Réglé'),
                desc: t('Matched and accepted settlement', 'Règlement rapproché et accepté'),
                amount: metrics.settled,
              },
            ].map((item) => (
              <div className="lifecycle-step" key={item.number}>
                <span className="step-number">{item.number}</span>
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.desc}</small>
                </div>
                <span className="amount">{money(item.amount, locale)}</span>
              </div>
            ))}
          </div>
          <p className="panel-footnote">
            {t(
              'Amounts reflect persisted state. A calculation is not a payment.',
              'Les montants reflètent l’état conservé. Un calcul n’est pas un paiement.',
            )}
          </p>
        </Panel>
      </div>
      <div className="overview-bottom">
        <Panel
          title={t('Recent activity', 'Activité récente')}
          action={
            <TextLink onClick={() => onView('ledger')}>
              {t('Audit trail', 'Piste d’audit')}
            </TextLink>
          }
          className="activity-panel"
        >
          {overview.activity.length ? (
            <div className="activity-list">
              {overview.activity.slice(0, 4).map((event, index) => (
                <div className="activity-item" key={event.id || index}>
                  <span className="activity-icon">
                    <Check size={15} />
                  </span>
                  <div>
                    <strong>
                      <AuditAction action={event.action || 'EVENT'} />
                    </strong>
                    <small>
                      {event.actor} <span>·</span> {date(event.created_at, locale)}
                    </small>
                  </div>
                  <span className="mono muted">#{short(String(event.id), 8)}</span>
                </div>
              ))}
            </div>
          ) : (
            <Empty title={t('Your audit trail starts here', 'Votre piste d’audit commence ici')} />
          )}
        </Panel>
        <section className="system-panel">
          <div className="system-header">
            <span className="system-icon">
              <Braces size={21} />
            </span>
            <span className="eyebrow">{t('ENGINE ROOM', 'SALLE DES MACHINES')}</span>
          </div>
          <h2>{t('Precision you can inspect.', 'Une précision vérifiable.')}</h2>
          <p>
            {t(
              'Native COBOL calculations. Preserved source bytes. Every result has a provenance.',
              'Calculs COBOL natifs. Octets sources conservés. Chaque résultat a une provenance.',
            )}
          </p>
          <div className="system-health">
            <span>
              <span className={`health-dot ${engineOk ? 'healthy' : ''}`} />
              {t('Engine', 'Moteur')}
              <strong>
                {engineOk ? t('Available', 'Disponible') : t('Unavailable', 'Indisponible')}
              </strong>
            </span>
            <span>
              <span className={`health-dot ${workerOk ? 'healthy' : ''}`} />
              {t('Worker', 'Processus')}
              <strong>{workerOk ? t('Online', 'En ligne') : t('Not ready', 'Non prêt')}</strong>
            </span>
          </div>
          <button className="system-link" onClick={() => onView('workbench')}>
            {t('Open workbench', 'Ouvrir l’atelier')}
            <ArrowRight size={17} />
          </button>
        </section>
      </div>
    </>
  )
}
function Metric({
  label,
  value,
  note,
  icon,
  onClick,
  attention = false,
}: {
  label: string
  value: string
  note: string
  icon: React.ReactNode
  onClick: () => void
  attention?: boolean
}) {
  return (
    <button className={`metric-card ${attention ? 'attention' : ''}`} onClick={onClick}>
      <span className="metric-label">
        {label}
        <span className="metric-icon">{icon}</span>
      </span>
      <strong className="metric-value">{value}</strong>
      <span className="metric-note">
        {attention && <span className="status-dot" />}
        {note}
        <ArrowUpRight size={14} />
      </span>
    </button>
  )
}

function UploadDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: (batch: Batch) => void
}) {
  const t = useText()
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      onSuccess(await api<Batch>('/batches', { method: 'POST', body: form }))
    } catch (cause) {
      setError(cause as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog
      title={t('Import a legacy batch', 'Importer un lot historique')}
      subtitle={t('PRESERVE. VALIDATE. CALCULATE.', 'CONSERVER. VALIDER. CALCULER.')}
      onClose={onClose}
    >
      <form onSubmit={(event) => void submit(event)} className="dialog-body">
        <p className="lead-copy">
          {t(
            'Upload an ASCII v1 file or the documented mixed IBM-037 / COMP-3 fixture. The engine verifies the complete envelope and control totals before approval.',
            'Téléversez un fichier ASCII v1 ou l’exemple mixte IBM-037 / COMP-3 documenté. Le moteur vérifie l’enveloppe complète et les totaux de contrôle avant l’approbation.',
          )}
        </p>
        <ErrorNotice error={error} />
        <label
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            setFile(event.dataTransfer.files[0] || null)
          }}
        >
          <span className="upload-icon">
            <Upload size={27} />
          </span>
          <strong>
            {file
              ? file.name
              : t('Choose a file or drop it here', 'Choisir un fichier ou le déposer ici')}
          </strong>
          <span>
            {file
              ? `${file.size.toLocaleString()} ${t('bytes', 'octets')}`
              : t(
                  '80-byte fixed-width ASCII · Header, details, trailer',
                  'ASCII à largeur fixe de 80 octets · En-tête, détails, fin',
                )}
          </span>
          <input
            ref={input}
            type="file"
            required={!file}
            aria-label={t('Batch source file', 'Fichier source du lot')}
            accept=".txt,.dat,.asc,.bin"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <div className="info-callout">
          <ShieldCheck size={19} />
          <span>
            {t(
              'Original bytes and SHA-256 are retained. Identical uploads return the existing receipt. No entries are posted during import.',
              'Les octets originaux et le SHA-256 sont conservés. Un fichier identique retourne le reçu existant. Aucune écriture n’est comptabilisée à l’importation.',
            )}
          </span>
        </div>
        <div className="fixture-links">
          <span>{t('Try a synthetic fixture:', 'Essayer un exemple synthétique :')}</span>
          <a href="/api/fixtures/hand-check.dat" download>
            <Download size={14} />
            {t('Golden cases', 'Cas de référence')}
          </a>
        </div>
        <div className="dialog-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            {t('Cancel', 'Annuler')}
          </button>
          <button className="button primary" disabled={!file || busy}>
            <Upload size={17} />
            {busy ? t('Importing…', 'Importation…') : t('Import & validate', 'Importer et valider')}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

function CommandPalette({
  onClose,
  onView,
  onSearch,
  onImport,
  canImport,
}: {
  onClose: () => void
  onView: (view: View) => void
  onSearch: (query: string) => void
  onImport: () => void
  canImport: boolean
}) {
  const t = useText()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const actions = navItems
    .filter((item) => `${item.en} ${item.fr}`.toLowerCase().includes(query.toLowerCase()))
    .map((item) => ({ label: t(item.en, item.fr), icon: item.icon, action: () => onView(item.id) }))
  if (query)
    actions.push({
      label: `${t('Search references for', 'Rechercher les références')} “${query}”`,
      icon: Search,
      action: () => onSearch(query),
    })
  if (canImport && !query)
    actions.push({ label: t('Import a batch', 'Importer un lot'), icon: Upload, action: onImport })
  return (
    <Dialog title={t('Command palette', 'Palette de commandes')} onClose={onClose}>
      <div className="command-search">
        <Search size={20} />
        <input
          autoFocus
          aria-label={t('Search commands or references', 'Rechercher des commandes ou références')}
          placeholder={t('Where would you like to go?', 'Où souhaitez-vous aller?')}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setSelected(0)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setSelected((value) => (value + 1) % actions.length)
            }
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              setSelected((value) => (value - 1 + actions.length) % actions.length)
            }
            if (event.key === 'Enter') actions[selected]?.action()
          }}
        />
      </div>
      <div className="command-list">
        {actions.map((action, index) => (
          <button
            key={action.label}
            className={index === selected ? 'selected' : ''}
            onClick={action.action}
          >
            <action.icon size={19} />
            {action.label}
            <ArrowRight size={16} />
          </button>
        ))}
      </div>
      <div className="command-footer">
        <span>
          <kbd>↑</kbd>
          <kbd>↓</kbd> {t('navigate', 'parcourir')}
        </span>
        <span>
          <kbd>↵</kbd> {t('open', 'ouvrir')}
        </span>
        <span>
          <kbd>esc</kbd> {t('close', 'fermer')}
        </span>
      </div>
    </Dialog>
  )
}
