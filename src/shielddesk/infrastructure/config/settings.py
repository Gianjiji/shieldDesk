"""Risoluzione della passphrase di sviluppo. Nessun segreto hard-coded nel codice.

Il flusso reale di key management (Argon2id + recovery key generata in
onboarding, ADR-007) arriva in Fase 5. Qui serve solo a far funzionare la
vertical slice locale con una cifratura reale, non finta.
"""

import os
import secrets

_ENV_VAR = "SHIELDDESK_DEV_PASSPHRASE"


def resolve_dev_passphrase() -> tuple[str, bool]:
    """Restituisce (passphrase, is_ephemeral).

    Se `SHIELDDESK_DEV_PASSPHRASE` non è impostata, genera una passphrase
    effimera valida solo per il processo corrente: i dati cifrati in questa
    sessione non saranno leggibili alla prossima esecuzione. Va segnalato
    all'utente, non taciuto.
    """
    configured = os.environ.get(_ENV_VAR)
    if configured:
        return configured, False
    return secrets.token_urlsafe(32), True
