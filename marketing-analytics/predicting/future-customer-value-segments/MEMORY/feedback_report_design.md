---
name: feedback_report_design
description: "Report design validated; prediction parameters, data period, and download links are now standard sections"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 718cda63-9d83-4fdf-adce-f70916e9c981
  modified: 2026-09-21T22:28:10.162Z
---

## Feature requests validated & implemented

### 1. Output file downloads
**Rule**: Include links to ALL generated output files in the final report, not just a summary.

**Why**: Users (account managers, clients) want to download raw data (CSVs), logs, and diagnostic images directly from the report, not hunt for files on disk or via separate downloads.

**How to apply**: 
- Add a "Arquivos e dados gerados" section at the bottom of the report
- List all files in DOWNLOADABLE_FILES with human-readable labels
- Generate `/runs/<slug>/download/<filename>` links for each
- Include PNGs (diagnostic charts) in the downloadable list

**Status**: Implemented & tested. 7 files now downloadable from report.

---

### 2. Prediction parameters display
**Rule**: Show model configuration and fitted coefficients directly in the report, extracted from prediction_params.txt.

**Why**: Model transparency. Clients and account managers need to see what was actually fit (r, alpha, a, b for frequency model; p, q, v for Gamma-Gamma) to understand if the model is reasonable and to debug if MAPE is high.

**How to apply**:
- Parse `prediction_params.txt` in report.py
- Create a "Parâmetros da previsão" section with:
  - Model configuration (horizon, granularity, frequency model type)
  - Data used (customer count, transaction count)
  - Frequency model parameters (r, alpha, a, b) with 6 decimal places
  - Gamma-Gamma parameters (p, q, v) with 6 decimal places
- Style as a single card/panel with sections inside
- Place after diagnostic charts, before downloads

**Status**: Implemented & tested. Section displays cleanly with proper formatting.

---

### 3. Data period in metadata panel
**Rule**: Show the time span of input data (first and last date) in the metadata panel at the top of the report.

**Why**: Quick reference. Users immediately see whether they're looking at Jan 1997–Jun 1998 data vs. last-year data. Extracted from validation_params.txt (Cohort Start Date, Holdout End Date).

**How to apply**:
- Add "Período dos dados" row to meta_rows in report.py
- Extract from validation_params["Cohort Start Date"] and ["Holdout End Date"]
- Display as "YYYY-MM-DD até YYYY-MM-DD"
- Place alongside "Nome da execução" and "Gerado em" in the metadata grid

**Status**: Implemented & tested. Shows as third column in metadata panel.

---

## Design patterns established

### Report structure (final)
1. Header (title + metadata panel with period)
2. KPI summary (customers, transactions, MAPE, horizon)
3. Segmentation chart + table
4. Extra dimension breakdown (if data exists)
5. Diagnostic charts (real vs. predicted transactions)
6. **Prediction parameters** ← NEW
7. **Files & downloads** ← NEW

### CSS conventions
- Use `.kicker` for section label (uppercase, accent color)
- Use `.lede` for section subtitle
- Use `.params-panel` for grouped parameters (light background, spaced sections)
- Use `.file-row` for download link rows (flex, with label on left, button on right)
- Use `.btn-download` for download buttons (teal/accent color, hover brightens)

### Slug-based URLs
Report generation now accepts `slug` parameter to generate proper download URLs. Slug = run folder name (e.g., "test-novo"). Used to build `/runs/<slug>/download/<filename>`.

---

## Validated workflow

1. User runs pipeline locally: `bash run_locally.sh <run-name>`
2. Script generates output folder: `output/<run-name>/`
3. Report is built with slug passed: `report.py --output_folder ... --slug <run-name>`
4. HTML includes working download links
5. User opens report in browser, can download any file
6. When pushed to GitHub, GitHub Actions redeploys to Cloud Run with same features

**No additional changes needed for this workflow.** It's now the standard.
