---
name: project_focvs_overview
description: FoCVS is an open-source BTYD CLV modeling tool; Gustavo is preparing controlled customer pilots with account managers
metadata: 
  node_type: memory
  type: project
  originSessionId: 718cda63-9d83-4fdf-adce-f70916e9c981
  modified: 2026-09-21T22:28:30.642Z
---

## Project: FoCVS (Future Customer Value Segments)

**Status**: Pilot phase (local + GCP Cloud Run deployment ready)  
**Owner**: Gustavo Hervás / Monks marketing agency  
**Repository**: `hervasgc/cloud-for-marketing` (Google community repo fork)

---

## What is FoCVS?

**Not** a GA4 segmentation tool. **Is** a probabilistic CLV (Customer Lifetime Value) modeling system built on BTYD (Buy Till You Die) models.

### Input
- Transactional data (customer_id, transaction_date, transaction_value)
- 12-18+ months of historical transactions
- Optional: extra dimension (e.g., product category)

### Processing
- Apache Beam pipeline (Dataflow or DirectRunner locally)
- Fits BG/NBD, MBG/NBD, or Pareto/NBD frequency models
- Pairs with Gamma-Gamma for spend prediction
- Validates on holdout set (calculates MAPE)
- Segments customers by predicted CLV

### Output
- Per-customer CLV predictions
- Segmentation (5-10 tiers by predicted lifetime value)
- Diagnostic charts (actual vs. predicted repeat transactions)
- Model parameters (fitted coefficients)
- Metadata (data period, model config, validation MAPE)

---

## Pilot Strategy (Gustavo's goal)

1. **Validation Phase** (now): Confirm FoCVS works end-to-end with account managers running local tests
2. **Pilot Selection**: Work with account teams to identify 1-2 clients with:
   - Persistent customer IDs (CRM/e-commerce)
   - 12+ months transactional history
   - Willingness to share data for analysis
3. **Pilot Execution** (future): Run FoCVS on real client data, present CLV segments to client as a go/no-go proof of concept
4. **Scaling** (if successful): Productionize, add dashboard/visualization layer, potentially activate segments in marketing channels

---

## Technical Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Pipeline | Apache Beam (Python) | DirectRunner locally, Dataflow on GCP |
| Models | lifetimes library | BTYD implementations |
| Web UI | Flask + Jinja2 | Local/Cloud Run development server |
| Report | HTML + CSS + JavaScript | Self-contained (base64 images), no external dependencies |
| Deployment | Cloud Run + GitHub Actions | Auto-deploy on main push (see [[reference_github_deployment]]) |
| Persistence | Cloud Storage (GCS) | Volume-mounted at /mnt/focvs-output on Cloud Run |

---

## Key Files & Responsibilities

### Core Pipeline
- `fcvs_pipeline_csv.py` - Main Apache Beam pipeline; reads CSV, fits models, outputs results

### Web UI (local + Cloud Run)
- `webapp/app.py` - Flask server; upload CSV, configure mapping, trigger pipeline, view results
- `webapp/report.py` - Standalone HTML report generator; reads output files, renders self-contained HTML
- `webapp/templates/` - HTML templates for upload form, run list, error pages

### Configuration & Deployment
- `run_locally.sh` - Convenience script: runs pipeline + generates report locally
- `Dockerfile` - Multi-stage build for Cloud Run
- `.github/workflows/deploy-focvs.yml` - GitHub Actions: builds, pushes, deploys to Cloud Run
- `requirements_local.txt`, `webapp/requirements_webapp.txt` - Dependencies

### Sample Data
- `samples/input_cdnow.csv` - Example transactional data (CD NOW historical purchases); used for local testing and cloud validation

---

## Current State (as of 2026-09-21)

### Implemented ✓
- Local Flask web UI for CSV upload + pipeline triggering
- Isolated output folders per run (with run-specific slug)
- HTML report generation with:
  - KPI summary (customer count, MAPE, horizon)
  - Segmentation visualization (bar chart)
  - Prediction parameters section (model config + fitted coefficients)
  - Data period metadata
  - Downloadable output files (7 files: CSVs, TXTs, diagnostic PNGs)
- GitHub Actions CI/CD with automatic Cloud Run deployment
- Cloud Storage volume mounting for persistent output

### Not Yet Implemented
- Dashboard/Looker Studio integration for client-facing visualization
- Activation workflows (e.g., push segments to Ads Customer Match)
- Automated email reports to stakeholders
- Multi-project/multi-client management (currently one-off deployments)

---

## Known Constraints & Gotchas

1. **Data prep is manual**: No automated CSV validation or column detection. User must ensure proper format (customer_id, date, value columns).

2. **Large data handling**: Pipeline works locally on 1.7M-row CSV (~250MB), but very large datasets (billions of rows) would need batching/preprocessing (not yet tackled).

3. **Model calibration**: If MAPE > 15% (default threshold), pipeline fails. User must tweak:
   - `penalizer_coef` (regularization strength)
   - `transaction_frequency_threshold` (MAPE cutoff)
   - Date ranges (calibration vs. holdout periods)

4. **No concurrent runs**: Cloud Run is set to max 3 instances, but pipeline timeout is 3600s. Two large pipelines running simultaneously could time out.

5. **Account manager UX**: Report is self-contained HTML, but no "friendly" dashboard. If showing to client, might need Looker Studio wrapper or custom PowerBI dashboard.

---

## Milestones & Next Steps

### Immediate (Week of 2026-09-21)
- ✓ Report parameters & downloads implemented
- ✓ Local testing validated
- ✓ GitHub push completed
- GCP Cloud Run deployment auto-triggered (in progress)

### Short-term (Next 2-4 weeks)
- [ ] Pilot client data ingestion & test run
- [ ] Looker Studio dashboard template (for client-friendly presentation)
- [ ] Document data prep checklist for account managers

### Medium-term (1-2 months)
- [ ] Feedback from pilot clients on model quality, visualization
- [ ] Automated email reports to stakeholders
- [ ] Segment activation workflow (e.g., CRM sync, Ads audience export)

### Long-term (if pilots are successful)
- [ ] Multi-tenant support (separate output folders per client)
- [ ] UI for parameter tweaking (don't rerun full pipeline, just adjust model)
- [ ] API for automated scheduling (e.g., "rerun CLV analysis monthly")
