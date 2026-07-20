"""Presentation layer web: sostituisce la UI QML/PySide6 con un'applicazione web
responsive servita in locale.

Il layer web non contiene business logic: come i vecchi ViewModel, si limita a
orchestrare i command applicativi e a serializzare lo stato in JSON. Il dominio,
l'applicazione e l'infrastruttura restano invariati.
"""
