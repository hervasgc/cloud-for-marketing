---
name: user_profile
description: Gustavo is a marketing agency professional building CLV modeling solutions for customer pilots
metadata: 
  node_type: memory
  type: user
  originSessionId: 718cda63-9d83-4fdf-adce-f70916e9c981
  modified: 2026-09-21T22:27:56.549Z
---

## Profile

- **Name**: Gustavo Hervás
- **Role**: Marketing agency professional / Account manager responsibility
- **Organization**: Monks (email: gustavo.hervas@monks.com)
- **Technical involvement**: Hands-on with deployment, local testing, GitHub Actions CI/CD, GCP infrastructure

## Goals with FoCVS

1. **Immediate**: Validate FoCVS as a viable CLV (Customer Lifetime Value) modeling tool for controlled customer pilots
2. **Medium-term**: Deploy to GCP Cloud Run as a "nearly ready" solution that account managers can bring to clients with minimal additional setup
3. **Long-term**: Run pilot CLV analyses with real customer data (transactional records from CRM/e-commerce systems)

## Key Constraints & Context

- Clients need **transactional data** with persistent customer IDs, not GA4 events (clarified early)
- Data volumes can be large (250MB+) but initial pilots use smaller subsets
- Prefers **local testing** before committing to GCP (validates functionality end-to-end)
- Values **visual, polished reports** that can be shown to account managers and clients directly
- Wants **minimal technical friction**: one-command local runs, clear download links, explicit model parameters visible

## Preferences & Behaviors

- **Decision-making**: Pragmatic; cancels out-of-scope work (e.g., large-data-size refactors) to focus on highest-value features (e.g., output file downloads, metadata panels)
- **Communication**: Portuguese-first prompts, direct requests with clear intent ("mostre também outras informações de output no relatorio final")
- **Validation approach**: Runs local tests with sample data; checks visual output in browser before greenlighting GitHub push
- **Ownership**: Creates GCP service accounts, manages secrets, does their own CI/CD setup (not asking for hand-holding on infrastructure)

## Technical depth

- Understands Apache Beam pipelines, BTYD models, Dataflow, Cloud Run
- Comfortable with Flask web UI, Python scripting, git workflows
- Not deeply familiar with all FoCVS internals but learns quickly when shown actual output (e.g., prediction_params.txt format)
