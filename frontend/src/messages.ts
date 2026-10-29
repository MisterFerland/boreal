/** Stable machine identifiers are preserved; human descriptions are localised. */
export const messages: Record<string, [string, string]> = {
  ACCEPTED: ['Valid instruction', 'Instruction valide'],
  RECORD_TYPE: ['Unsupported record type', 'Type d’enregistrement non pris en charge'],
  IDENTITY_REQUIRED: [
    'Source and instruction reference are required',
    'Le système source et la référence sont obligatoires',
  ],
  IDENTITY_SYNTAX: [
    'Invalid source or reference syntax',
    'Syntaxe invalide du système source ou de la référence',
  ],
  PROGRAM_UNSUPPORTED: [
    'Unsupported reimbursement program',
    'Programme de remboursement non pris en charge',
  ],
  DATE_INVALID: ['Invalid business date', 'Date opérationnelle invalide'],
  AMOUNT_SYNTAX: ['Invalid amount representation', 'Représentation du montant invalide'],
  AMOUNT_OVERFLOW: ['Amount exceeds the supported range', 'Le montant dépasse la plage permise'],
  COST_NOT_POSITIVE: ['Cost must be strictly positive', 'Le coût doit être strictement positif'],
  DUPLICATE_REFERENCE: ['Duplicate instruction reference', 'Référence d’instruction en double'],
  POLICY_UNSUPPORTED: ['Unsupported policy version', 'Version de politique non prise en charge'],
  BUSINESS_KEY_CONFLICT: [
    'This source and reference already belong to another instruction',
    'Ce système source et cette référence appartiennent déjà à une autre instruction',
  ],
  FILE_FRAMING: [
    'Invalid file length, delimiters or final line ending',
    'Longueur, séparateurs ou fin de ligne du fichier invalides',
  ],
  FILE_ENCODING: [
    'The file contains invalid ASCII bytes',
    'Le fichier contient des octets ASCII invalides',
  ],
  HEADER_INVALID: ['Invalid file header', 'En-tête de fichier invalide'],
  TRAILER_MISSING: [
    'The file trailer is missing',
    'L’enregistrement de fin de fichier est manquant',
  ],
  DATA_AFTER_TRAILER: [
    'Data appears after the file trailer',
    'Des données suivent l’enregistrement de fin',
  ],
  CONTROL_AMOUNT_SYNTAX: [
    'An amount cannot be used to verify file controls',
    'Un montant ne permet pas de vérifier les contrôles du fichier',
  ],
  CONTROL_OVERFLOW: [
    'The control total exceeds the supported range',
    'Le total de contrôle dépasse la plage permise',
  ],
  TRAILER_INVALID: ['Invalid file trailer', 'Enregistrement de fin invalide'],
  CONTROL_COUNT_MISMATCH: [
    'Trailer count differs from physical detail count',
    'Le nombre de détails diffère du total de fin de fichier',
  ],
  CONTROL_TOTAL_MISMATCH: [
    'Trailer amount differs from the physical detail total',
    'Le montant de fin diffère du total des détails physiques',
  ],
  EMPTY_BATCH: ['The file contains no instructions', 'Le fichier ne contient aucune instruction'],
  RECORD_TYPE_INVALID: [
    'Invalid record type in the file envelope',
    'Type d’enregistrement invalide dans l’enveloppe du fichier',
  ],
  PACKED_DIGIT: [
    'Invalid packed-decimal digit nibble',
    'Quartet numérique décimal condensé invalide',
  ],
  PACKED_SIGN: ['Invalid packed-decimal sign nibble', 'Quartet de signe décimal condensé invalide'],
  PACKED_LENGTH: [
    'Invalid packed-decimal field length',
    'Longueur du champ décimal condensé invalide',
  ],
  PACKED_VALID: [
    'Packed-decimal representation is valid',
    'La représentation décimale condensée est valide',
  ],
  MIXED_FRAMING: [
    'Invalid mixed-format record length',
    'Longueur de l’enregistrement mixte invalide',
  ],
  MIXED_ENCODING: ['Invalid IBM-037 character field', 'Champ de caractères IBM-037 invalide'],
  AUTH_REQUIRED: ['Sign in to continue.', 'Connectez-vous pour continuer.'],
  SESSION_EXPIRED: [
    'Your session has expired. Sign in again.',
    'Votre session a expiré. Connectez-vous de nouveau.',
  ],
  ORIGIN_REJECTED: [
    'This request origin is not permitted.',
    'L’origine de cette demande n’est pas autorisée.',
  ],
  CSRF_REJECTED: [
    'The session token is invalid. Sign in again.',
    'Le jeton de session est invalide. Connectez-vous de nouveau.',
  ],
  ROLE_FORBIDDEN: [
    'Your role is not authorized for this action.',
    'Votre rôle n’est pas autorisé à effectuer cette action.',
  ],
  INVALID_CREDENTIALS: [
    'Invalid username or password.',
    'Nom d’utilisateur ou mot de passe invalide.',
  ],
  LOGIN_THROTTLED: [
    'Too many attempts. Try again in five minutes.',
    'Trop de tentatives. Réessayez dans cinq minutes.',
  ],
  BATCH_NOT_FOUND: ['The batch was not found.', 'Le lot est introuvable.'],
  JOB_NOT_FOUND: ['The job was not found.', 'Le traitement est introuvable.'],
  JOURNAL_NOT_FOUND: ['The journal was not found.', 'L’écriture est introuvable.'],
  RECORD_NOT_FOUND: ['The instruction was not found.', 'L’instruction est introuvable.'],
  RECONCILIATION_NOT_FOUND: [
    'The reconciliation result was not found.',
    'Le résultat du rapprochement est introuvable.',
  ],
  SOURCE_NOT_FOUND: [
    'This source is not in the recorded build allowlist.',
    'Ce code source ne figure pas dans la liste autorisée de la version conservée.',
  ],
  FIXTURE_NOT_FOUND: [
    'The synthetic fixture was not found.',
    'Le fichier d’exemple synthétique est introuvable.',
  ],
  NOT_FOUND: ['The requested resource was not found.', 'La ressource demandée est introuvable.'],
  IDEMPOTENCY_REQUIRED: [
    'A valid request idempotency key is required.',
    'Une clé d’idempotence valide est obligatoire.',
  ],
  IDEMPOTENCY_CONFLICT: [
    'This request key was already used with different content.',
    'Cette clé de demande a déjà été utilisée avec un contenu différent.',
  ],
  UPLOAD_SIZE: [
    'The import must contain between 1 byte and 12 MiB.',
    'Le fichier doit contenir entre 1 octet et 12 Mio.',
  ],
  INPUT_TOO_LARGE: ['The input exceeds the supported size.', 'L’entrée dépasse la taille permise.'],
  SNAPSHOT_INVALID: [
    'Frozen calculation or proposal integrity verification failed.',
    'La vérification d’intégrité du calcul figé ou des propositions a échoué.',
  ],
  SELF_APPROVAL: [
    'The person who submitted this batch cannot approve it.',
    'La personne ayant soumis ce lot ne peut pas l’approuver.',
  ],
  NOT_REVIEWABLE: [
    'Only a reviewed batch with accepted records can be approved.',
    'Seul un lot examiné avec des enregistrements acceptés peut être approuvé.',
  ],
  DEMO_CONTROL_DISABLED: [
    'Interruption controls require the local demonstration profile.',
    'Les commandes d’interruption nécessitent le profil de démonstration locale.',
  ],
  NOT_APPROVED: [
    'This batch is not approved for posting.',
    'Ce lot n’est pas approuvé pour comptabilisation.',
  ],
  APPROVAL_INVALID: [
    'Approval does not match the frozen input and proposals.',
    'L’approbation ne correspond pas à l’entrée et aux propositions figées.',
  ],
  NO_CALCULATION: ['A completed calculation is required.', 'Un calcul terminé est obligatoire.'],
  NOT_RETRYABLE: [
    'This job is not awaiting a retry.',
    'Ce traitement n’est pas en attente d’une reprise.',
  ],
  NOT_REVERSIBLE: [
    'Only an unsettled, unreversed obligation can be reversed.',
    'Seule une obligation non réglée et non contrepassée peut être annulée.',
  ],
  NOT_SETTLEABLE: [
    'Only an unresolved exact match for an unsettled obligation can be accepted.',
    'Seule une correspondance exacte ouverte pour une obligation non réglée peut être acceptée.',
  ],
  ALREADY_ACCEPTED: [
    'An accepted settlement cannot be rewritten.',
    'Un règlement accepté ne peut pas être réécrit.',
  ],
  INVALID_REQUEST: ['The request fields are invalid.', 'Les champs de la demande sont invalides.'],
  INTERNAL_ERROR: [
    'The service encountered an error. Use the correlation ID to investigate.',
    'Le service a rencontré une erreur. Utilisez l’identifiant de corrélation pour l’analyse.',
  ],
  REQUEST_FAILED: [
    'The request failed. Check the service connection.',
    'La demande a échoué. Vérifiez la connexion au service.',
  ],
  ENGINE_UNAVAILABLE: [
    'The compiled COBOL engine is unavailable.',
    'Le moteur COBOL compilé est indisponible.',
  ],
  ENGINE_TIMEOUT: [
    'The COBOL process exceeded its time limit.',
    'Le processus COBOL a dépassé son délai.',
  ],
  ENGINE_EXECUTION_FAILED: [
    'The COBOL process could not execute.',
    'Le processus COBOL n’a pas pu s’exécuter.',
  ],
  ENGINE_BUILD_HASH_MISMATCH: [
    'The recorded engine build failed hash verification.',
    'La vérification de l’empreinte de la version conservée du moteur a échoué.',
  ],
  ENGINE_BUILD_INVALID: [
    'The engine build identifier is invalid.',
    'L’identifiant de version du moteur est invalide.',
  ],
  POSTING_INCOMPLETE: [
    'Posting has unfinished records.',
    'Des enregistrements restent à comptabiliser.',
  ],
  RECORD_STATE_CONFLICT: [
    'The instruction state changed before commit.',
    'L’état de l’instruction a changé avant la validation.',
  ],
  REPLAY_VALIDATION_FAILED: [
    'Historical input validation failed during replay.',
    'La validation de l’entrée historique a échoué lors du rejeu.',
  ],
  RETRY_LIMIT: [
    'The maximum number of attempts has been reached.',
    'Le nombre maximal de tentatives a été atteint.',
  ],
  SETTLEMENT_COLUMNS: [
    'The settlement CSV has invalid columns.',
    'Le CSV de règlements contient des colonnes invalides.',
  ],
  SETTLEMENT_ENCODING: [
    'The settlement CSV is not valid UTF-8.',
    'Le CSV de règlements n’est pas un fichier UTF-8 valide.',
  ],
  SETTLEMENT_LIMIT: [
    'The settlement file exceeds the supported record count.',
    'Le fichier de règlements dépasse le nombre d’enregistrements permis.',
  ],
  SETTLEMENT_REFERENCE: ['Invalid settlement reference.', 'Référence de règlement invalide.'],
  SETTLEMENT_SYNTAX: [
    'Invalid settlement amount representation.',
    'Représentation du montant de règlement invalide.',
  ],
  RECONCILIATION_AMOUNT_SYNTAX: [
    'Invalid amount passed to reconciliation.',
    'Montant invalide soumis au rapprochement.',
  ],
  RECONCILIATION_REFERENCE_SYNTAX: [
    'Invalid reference passed to reconciliation.',
    'Référence invalide soumise au rapprochement.',
  ],
  REVERSAL_UNSUPPORTED: [
    'This reversal state is not supported.',
    'Cet état ne permet pas une contrepassation.',
  ],
}
export const actions: Record<string, [string, string]> = {
  'session.created': ['Session started', 'Session ouverte'],
  'session.ended': ['Session ended', 'Session fermée'],
  'login.failed': ['Sign-in failed', 'Échec de connexion'],
  'accounts.created': ['Local accounts created', 'Comptes locaux créés'],
  'job.submitted': ['Job queued', 'Traitement mis en attente'],
  'batch.imported': ['Batch imported', 'Lot importé'],
  'batch.approved': ['Batch approved', 'Lot approuvé'],
  'job.retry_requested': ['Recovery requested', 'Reprise demandée'],
  'journal.reversed': ['Compensating journal posted', 'Écriture compensatrice comptabilisée'],
  'settlement.imported': ['Settlement file imported', 'Fichier de règlements importé'],
  'settlement.accepted': ['Exact settlement accepted', 'Règlement exact accepté'],
  'exception.reviewed': ['Exception reviewed', 'Exception examinée'],
  'job.exhausted': ['Retry limit reached', 'Limite de reprises atteinte'],
  'job.claimed': ['Worker claimed job', 'Traitement attribué au processus'],
  'job.completed': ['Job completed', 'Traitement terminé'],
  'batch.quarantined': ['Batch quarantined', 'Lot mis en quarantaine'],
  'batch.calculated': ['COBOL calculation completed', 'Calcul COBOL terminé'],
  'demo.interruption_armed': ['Local interruption armed', 'Interruption locale préparée'],
  'posting.chunk_committed': ['Posting chunk committed', 'Segment comptable validé'],
  'settlement.classified': ['Settlements classified', 'Règlements classés'],
  'job.attempt_failed': ['Processing attempt failed', 'Tentative de traitement échouée'],
  'evidence.requested': ['Evidence export requested', 'Exportation des preuves demandée'],
}
