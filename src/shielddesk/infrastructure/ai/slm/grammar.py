"""Grammar GBNF (llama.cpp) che vincola l'output dell'SLM a JSON valido conforme
allo schema di risposta: mai testo libero, mai un JSON parzialmente inventato.

Il campo `reason` viene PRIMA del verdetto di proposito: obbliga il modello a
generare qualche token di ragionamento sul contesto prima di impegnarsi su
`risk_level`. Su modelli piccoli (1.5B) questo "pensa prima di etichettare" è
ciò che permette di usare davvero il contesto (es. declassare uno scherzo tra
amici) invece di riconoscere solo parole tossiche isolate. `reason` è limitato
in lunghezza per non esaurire il budget di token prima del verdetto.
"""

RESPONSE_GRAMMAR = r"""
root ::= "{" ws "\"reason\"" ws ":" ws reason "," ws "\"risk_level\"" ws ":" ws risk-level "," ws "\"category\"" ws ":" ws category "," ws "\"confidence\"" ws ":" ws confidence ws "}"
reason ::= "\"" rchar{0,200} "\""
rchar ::= [^"\\\n]
risk-level ::= "\"SAFE\"" | "\"LOW\"" | "\"MEDIUM\"" | "\"HIGH\"" | "\"CRITICAL\""
category ::= "\"insult\"" | "\"exclusion\"" | "\"threat\"" | "\"blackmail\"" | "\"hate\"" | "\"self_harm\"" | "\"none\""
confidence ::= "0." [0-9] [0-9]? | "1.0"
ws ::= [ \t\n]*
"""
