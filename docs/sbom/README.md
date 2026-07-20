# SBOM

`sbom.cdx.json` è il Software Bill of Materials in formato [CycloneDX](https://cyclonedx.org/),
generato dall'ambiente virtuale del progetto (dipendenze runtime, non quelle di sviluppo
usate solo per conversione modelli/audit).

## Rigenerare

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
uv run --with cyclonedx-bom cyclonedx-py environment --of JSON --output-file docs/sbom/sbom.cdx.json .venv
```

Da rigenerare ogni volta che cambiano le dipendenze in `pyproject.toml`/`uv.lock`.
