#!/usr/bin/env python3
"""Generates the standard FoCVS HTML report for one pipeline run.

Reads the output files produced by fcvs_pipeline_csv.py in a given output
folder (prediction_summary.csv, prediction_summary_extra_dimension.csv,
prediction_params.txt, validation_params.txt and the two diagnostic PNGs)
and writes a single self-contained report.html into that same folder.

Has no dependency beyond the Python standard library, so it can run in any
environment that can run the pipeline itself -- the CLI-only flow
(run_locally.sh) and the optional web UI (webapp/app.py) both call into it.

Usage:
    python report.py --output_folder ./output/my-run/ [--run_name "My run"]
"""

import argparse
import base64
import csv
import json
import os
import re
from datetime import datetime


MODEL_LABELS = {
    'BGNBD': 'BG/NBD',
    'MBGNBD': 'MBG/NBD',
    'PNBD': 'Pareto/NBD',
    'BGBB': 'BG/BB',
}

# Sequential ramp endpoints (darkest = highest-value segment).
LIGHT_SEG_START, LIGHT_SEG_END = '#0F3B33', '#C3E3D9'
DARK_SEG_START, DARK_SEG_END = '#2E8677', '#DCF3EC'

MAX_EXTRA_DIMENSION_ROWS = 6


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(c))) for c in rgb)


def build_ramp(n, start_hex, end_hex):
    """Returns n hex colors linearly interpolated from start_hex to end_hex."""
    if n <= 1:
        return [start_hex]
    sr, sg, sb = _hex_to_rgb(start_hex)
    er, eg, eb = _hex_to_rgb(end_hex)
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(_rgb_to_hex((
            sr + (er - sr) * t,
            sg + (eg - sg) * t,
            sb + (eb - sb) * t,
        )))
    return out


def _read_csv_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _parse_key_value_txt(path):
    """Parses a "Key: Value" per line text file into a dict of strings."""
    result = {}
    if not os.path.isfile(path):
        return result
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\s*([^:]+):\s*(.*)$', line.rstrip('\n'))
            if m:
                result[m.group(1).strip()] = m.group(2).strip()
    return result


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int_display(value):
    try:
        return f'{int(round(float(value))):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return str(value)


def _fmt_money(value):
    try:
        return f'${float(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value, decimals=1):
    try:
        return f'{float(value):.{decimals}f}%'.replace('.', ',')
    except (TypeError, ValueError):
        return str(value)


def _b64_image(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _load_run_meta(output_folder):
    path = os.path.join(output_folder, 'run_meta.json')
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _extract_horizon(prediction_params):
    m = re.match(r'(\d+)\s*(\S+)', prediction_params.get('Prediction for', ''))
    if m:
        return f'{m.group(1)} {m.group(2)}'
    return prediction_params.get('Prediction for', 'N/D')


def _extract_mape(validation_params):
    raw = validation_params.get('Validation Mean Absolute Percent Error (MAPE)', '')
    m = re.match(r'([\d.]+)\s*%', raw)
    if m:
        return float(m.group(1)), f'{m.group(1).replace(".", ",")}%'
    return None, (raw or 'N/D')


def _extract_customers_transactions(validation_params, prediction_params):
    cust_val = prediction_params.get('Customers modeled', '')
    txn_val = prediction_params.get('Transactions observed', '')
    return _to_int_display(cust_val), _to_int_display(txn_val)


def generate(output_folder, run_name=None):
    """Builds report.html inside output_folder. Returns the report path."""
    output_folder = output_folder if output_folder.endswith('/') else output_folder + '/'
    run_name = run_name or os.path.basename(os.path.normpath(output_folder))

    meta = _load_run_meta(output_folder)
    prediction_params = _parse_key_value_txt(output_folder + 'prediction_params.txt')
    validation_params = _parse_key_value_txt(output_folder + 'validation_params.txt')
    summary_rows = _read_csv_rows(output_folder + 'prediction_summary.csv')
    extra_dim_rows = _read_csv_rows(output_folder + 'prediction_summary_extra_dimension.csv')

    model_key = prediction_params.get('Frequency Model', validation_params.get('Frequency Model', ''))
    model_label = MODEL_LABELS.get(model_key, model_key or 'N/D')
    horizon = _extract_horizon(prediction_params)
    granularity = prediction_params.get('Model Time Granularity', 'N/D')
    mape_value, mape_display = _extract_mape(validation_params)
    n_customers, n_transactions = _extract_customers_transactions(validation_params, prediction_params)

    mape_class = ''
    if mape_value is not None:
        threshold = _to_float(meta.get('transaction_frequency_threshold', 15))
        if mape_value > threshold:
            mape_class = 'critical'
        elif mape_value > threshold * 0.66:
            mape_class = 'warning'
        else:
            mape_class = 'good'

    # --- Segment chart + table ---
    segments = []
    for row in summary_rows:
        segments.append({
            'segment': row.get('segment', ''),
            'pct': _to_float(row.get('perc_of_total_customer_value')),
            'value': _to_float(row.get('average_predicted_customer_value')),
            'aov': _to_float(row.get('average_predicted_order_value')),
            'retention': _to_float(row.get('average_retention_probability')),
            'customers': row.get('number_of_customers', ''),
        })
    segments.sort(key=lambda s: _to_float(s['segment']))
    max_pct = max((s['pct'] for s in segments), default=1) or 1
    seg_ramp_light = build_ramp(len(segments), LIGHT_SEG_START, LIGHT_SEG_END)
    seg_ramp_dark = build_ramp(len(segments), DARK_SEG_START, DARK_SEG_END)

    seg_css_vars_light = '\n'.join(
        f'      --seg-{i}:{seg_ramp_light[i]};' for i in range(len(segments)))
    seg_css_vars_dark = '\n'.join(
        f'      --seg-{i}:{seg_ramp_dark[i]};' for i in range(len(segments)))

    bar_cols = []
    table_rows = []
    for i, s in enumerate(segments):
        height_pct = max(1.5, (s['pct'] / max_pct) * 100)
        bar_cols.append(f'''
        <div class="bar-col">
          <div class="bar-val">{_fmt_pct(s['pct'])}</div>
          <div class="bar" style="height:{height_pct:.1f}%; background:var(--seg-{i});"
               data-tip="Segmento {s['segment']} &middot; {_fmt_money(s['value'])} previstos/cliente &middot; retenção {_fmt_pct(s['retention']*100, 0)}"></div>
          <div class="bar-label">Segmento {s['segment']}</div>
          <div class="bar-sub">{_to_int_display(s['customers'])} clientes</div>
        </div>''')
        table_rows.append(f'''
          <tr>
            <td><span class="seg-swatch" style="background:var(--seg-{i})"></span>{s['segment']}</td>
            <td>{_to_int_display(s['customers'])}</td>
            <td>{s['retention']:.2f}</td>
            <td>{_fmt_money(s['value'])}</td>
            <td>{_fmt_money(s['aov'])}</td>
            <td>{_fmt_pct(s['pct'])}</td>
          </tr>''')

    top_segment_pct = _fmt_pct(segments[0]['pct']) if segments else 'N/D'
    n_segments = len(segments)

    # --- Extra dimension chart (optional) ---
    extra_dim_section = ''
    valid_extra_rows = [r for r in extra_dim_rows if r.get('extra_dimension')]
    if valid_extra_rows:
        valid_extra_rows.sort(key=lambda r: _to_float(r.get('total_customer_value')), reverse=True)
        top_rows = valid_extra_rows[:MAX_EXTRA_DIMENSION_ROWS]
        rest_rows = valid_extra_rows[MAX_EXTRA_DIMENSION_ROWS:]
        hbar_rows = []
        for r in top_rows:
            pct = _to_float(r.get('perc_of_total_customer_value'))
            hbar_rows.append(f'''
        <div class="hbar-row"><div class="name">{r.get('extra_dimension')}</div>
          <div class="hbar-track"><div class="hbar-fill" style="width:{max(pct,1):.2f}%"></div></div>
          <div class="pct">{_fmt_pct(pct)}</div></div>''')
        if rest_rows:
            rest_pct = sum(_to_float(r.get('perc_of_total_customer_value')) for r in rest_rows)
            hbar_rows.append(f'''
        <div class="hbar-row"><div class="name">Outras ({len(rest_rows)})</div>
          <div class="hbar-track"><div class="hbar-fill" style="width:{max(rest_pct,1):.2f}%; background:var(--ink-soft);"></div></div>
          <div class="pct">{_fmt_pct(rest_pct)}</div></div>''')
        extra_dim_section = f'''
  <section>
    <div class="kicker">Quebra por dimensão extra</div>
    <h2>Valor futuro total por dimensão extra</h2>
    <p class="lede">{len(valid_extra_rows)} valores distintos encontrados nesta coluna &mdash; mostrando os {len(top_rows)} maiores{" e o restante agrupado" if rest_rows else ""}.</p>
    <div class="chart-card">
      <div class="chart-title">Top categorias por valor futuro total</div>
      <div class="hbar-list">{''.join(hbar_rows)}
      </div>
    </div>
  </section>'''

    # --- Diagnostic images (optional) ---
    diag_cards = []
    rtot_b64 = _b64_image(output_folder + 'repeat_transactions_over_time.png')
    rctot_b64 = _b64_image(output_folder + 'repeat_cumulative_transactions_over_time.png')
    if rtot_b64:
        diag_cards.append(f'''
      <div class="diag-card">
        <img src="data:image/png;base64,{rtot_b64}" alt="Transações de recompra reais vs. modeladas ao longo do tempo" />
        <div class="diag-cap">Recompras reais vs. modeladas, por período</div>
      </div>''')
    if rctot_b64:
        diag_cards.append(f'''
      <div class="diag-card">
        <img src="data:image/png;base64,{rctot_b64}" alt="Transações de recompra acumuladas reais vs. modeladas" />
        <div class="diag-cap">Recompras acumuladas, reais vs. modeladas</div>
      </div>''')
    diag_section = ''
    if diag_cards:
        diag_section = f'''
  <section>
    <div class="kicker">Evidência de validação do modelo</div>
    <h2>Gráficos de diagnóstico gerados pelo pipeline</h2>
    <p class="lede">Comparam as transações reais de recompra contra o que o modelo previu no período de holdout &mdash; base do MAPE mostrado acima.</p>
    <div class="diag-grid">{''.join(diag_cards)}
    </div>
  </section>'''

    # --- Run metadata panel ---
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    meta_rows = [('Nome da execução', run_name), ('Gerado em', generated_at)]
    if meta.get('source_filename'):
        meta_rows.append(('Arquivo de origem', meta['source_filename']))
    if meta.get('column_mapping'):
        cm = meta['column_mapping']
        labels = {
            'customer_id': 'Cliente', 'transaction_date': 'Data',
            'sales': 'Valor', 'extra_dimension': 'Dimensão extra',
        }
        mapping_display = ' · '.join(
            f'{labels.get(k, k)}: {v}' for k, v in cm.items() if v)
        if mapping_display:
            meta_rows.append(('Colunas usadas', mapping_display))
    meta_rows_html = ''.join(
        f'<div class="meta-row"><span class="meta-k">{k}</span><span class="meta-v">{v}</span></div>'
        for k, v in meta_rows)

    html = _TEMPLATE
    replacements = {
        '__RUN_NAME__': run_name,
        '__GENERATED_AT__': generated_at,
        '__META_ROWS__': meta_rows_html,
        '__KPI_CUSTOMERS__': n_customers,
        '__KPI_TRANSACTIONS__': n_transactions,
        '__KPI_MAPE__': mape_display,
        '__KPI_MAPE_CLASS__': mape_class,
        '__KPI_HORIZON__': horizon,
        '__KPI_MODEL__': model_label,
        '__KPI_GRANULARITY__': granularity,
        '__TOP_SEGMENT_PCT__': top_segment_pct,
        '__N_SEGMENTS__': str(n_segments),
        '__SEG_CSS_LIGHT__': seg_css_vars_light,
        '__SEG_CSS_DARK__': seg_css_vars_dark,
        '__SEGMENT_BARS__': ''.join(bar_cols),
        '__SEGMENT_TABLE_ROWS__': ''.join(table_rows),
        '__EXTRA_DIMENSION_SECTION__': extra_dim_section,
        '__DIAGNOSTIC_SECTION__': diag_section,
    }
    for token, value in replacements.items():
        html = html.replace(token, str(value))

    report_path = output_folder + 'report.html'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return report_path


_TEMPLATE = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>FoCVS · __RUN_NAME__</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

  :root{
    --bg:#F6F7F5; --surface:#FFFFFF; --surface-alt:#EDEFEA;
    --ink:#16211F; --ink-muted:#4B5957; --ink-soft:#7C8B88; --border:#D8DED9;
    --accent:#1F6F63; --accent-soft:#E4EFEC;
    --accent-2:#C98A2C; --accent-2-soft:#F7ECDA;
    --good:#2E7D4F; --good-soft:#E2F0E5;
    --warning:#B5842B; --warning-soft:#F7ECDA;
    --critical:#A8452F; --critical-soft:#F5E4DF;
__SEG_CSS_LIGHT__
    --shadow: 0 1px 2px rgba(22,33,31,0.04), 0 8px 24px -12px rgba(22,33,31,0.14);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#0F1614; --surface:#17211E; --surface-alt:#1D2B26;
      --ink:#E9EEE9; --ink-muted:#A9B7B2; --ink-soft:#7E9490; --border:#2B3934;
      --accent:#4FB3A0; --accent-soft:rgba(79,179,160,0.14);
      --accent-2:#E3A94A; --accent-2-soft:rgba(227,169,74,0.14);
      --good:#6FCB93; --good-soft:rgba(111,203,147,0.14);
      --warning:#E3A94A; --warning-soft:rgba(227,169,74,0.14);
      --critical:#E08774; --critical-soft:rgba(224,135,116,0.14);
__SEG_CSS_DARK__
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -12px rgba(0,0,0,0.55);
    }
  }
  :root[data-theme="dark"]{
    --bg:#0F1614; --surface:#17211E; --surface-alt:#1D2B26;
    --ink:#E9EEE9; --ink-muted:#A9B7B2; --ink-soft:#7E9490; --border:#2B3934;
    --accent:#4FB3A0; --accent-soft:rgba(79,179,160,0.14);
    --accent-2:#E3A94A; --accent-2-soft:rgba(227,169,74,0.14);
    --good:#6FCB93; --good-soft:rgba(111,203,147,0.14);
    --warning:#E3A94A; --warning-soft:rgba(227,169,74,0.14);
    --critical:#E08774; --critical-soft:rgba(224,135,116,0.14);
__SEG_CSS_DARK__
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -12px rgba(0,0,0,0.55);
  }

  *{box-sizing:border-box;}
  body{margin:0; background:var(--bg); color:var(--ink); font-family:'IBM Plex Sans', system-ui, sans-serif; font-size:16px; line-height:1.6;}
  .shell{max-width:920px; margin:0 auto; padding:48px 24px 88px;}

  header.cover{border-bottom:1px solid var(--border); padding-bottom:22px; margin-bottom:20px;}
  .eyebrow{font-family:'IBM Plex Mono', monospace; font-size:12px; text-transform:uppercase; letter-spacing:0.1em; color:var(--accent); margin-bottom:14px;}
  h1{font-family:'Fraunces', serif; font-weight:500; font-size:clamp(26px,3.6vw,34px); line-height:1.18; letter-spacing:-0.01em; text-wrap:balance; margin:0 0 6px;}
  .subtitle{color:var(--ink-muted); font-size:15.5px; max-width:64ch; margin:0;}

  .meta-panel{display:flex; flex-wrap:wrap; gap:4px 28px; margin-top:20px; padding-top:16px; border-top:1px dashed var(--border);}
  .meta-row{display:flex; flex-direction:column; gap:2px;}
  .meta-k{font-family:'IBM Plex Mono', monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-soft);}
  .meta-v{font-size:13px; color:var(--ink-muted); max-width:48ch;}

  section{margin-top:44px;}
  .kicker{font-family:'IBM Plex Mono', monospace; font-size:12px; color:var(--accent); text-transform:uppercase; letter-spacing:0.08em; margin-bottom:10px;}
  h2{font-family:'Fraunces', serif; font-weight:500; font-size:22px; margin:0 0 8px; text-wrap:balance;}
  .lede{color:var(--ink-muted); font-size:15px; margin:0 0 20px; max-width:64ch;}

  .kpi-grid{display:grid; grid-template-columns:repeat(4,1fr); gap:2px; background:var(--border); border:1px solid var(--border); border-radius:12px; overflow:hidden; box-shadow:var(--shadow);}
  .kpi{background:var(--surface); padding:16px 14px;}
  .kpi .v{font-family:'Fraunces', serif; font-weight:500; font-size:24px; font-variant-numeric:tabular-nums; letter-spacing:-0.01em;}
  .kpi .v.good{color:var(--good);} .kpi .v.warning{color:var(--warning);} .kpi .v.critical{color:var(--critical);}
  .kpi .l{font-family:'IBM Plex Mono', monospace; font-size:10.5px; color:var(--ink-muted); text-transform:uppercase; letter-spacing:0.05em; margin-top:4px;}
  @media (max-width:640px){ .kpi-grid{grid-template-columns:repeat(2,1fr);} }

  .chart-card{background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:26px 26px 18px; box-shadow:var(--shadow);}
  .chart-title{font-weight:600; font-size:14.5px; margin-bottom:2px;}
  .chart-note{color:var(--ink-soft); font-size:13px; margin-bottom:22px;}

  .bars-pct{display:flex; align-items:flex-end; gap:12px; height:210px; padding:0 4px; border-bottom:1px solid var(--border);}
  .bar-col{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; position:relative;}
  .bar-val{font-family:'IBM Plex Mono', monospace; font-weight:500; font-size:13px; margin-bottom:6px; font-variant-numeric:tabular-nums;}
  .bar{width:100%; max-width:56px; border-radius:4px 4px 0 0; transition:filter 0.15s ease; cursor:default;}
  .bar:hover{filter:brightness(1.08);}
  .bar-label{font-family:'IBM Plex Mono', monospace; font-size:11px; color:var(--ink-muted); margin-top:10px;}
  .bar-sub{font-size:10.5px; color:var(--ink-soft); margin-top:2px;}

  .hbar-list{display:flex; flex-direction:column; gap:10px; margin-top:4px;}
  .hbar-row{display:grid; grid-template-columns:120px 1fr 64px; align-items:center; gap:12px;}
  .hbar-row .name{font-family:'IBM Plex Mono', monospace; font-size:12.5px; color:var(--ink-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
  .hbar-track{background:var(--surface-alt); border-radius:4px; height:16px; position:relative; overflow:hidden;}
  .hbar-fill{position:absolute; left:0; top:0; bottom:0; background:var(--accent-2); border-radius:4px; min-width:4px;}
  .hbar-row .pct{font-family:'IBM Plex Mono', monospace; font-size:12.5px; text-align:right; font-variant-numeric:tabular-nums;}

  .tooltip{position:fixed; pointer-events:none; z-index:50; background:var(--surface); color:var(--ink); border:1px solid var(--border); font-family:'IBM Plex Mono', monospace; font-size:12px; line-height:1.5; padding:9px 12px; border-radius:8px; box-shadow:var(--shadow); opacity:0; transform:translate(-50%,-8px); transition:opacity 0.1s ease; white-space:nowrap;}
  .tooltip.show{opacity:1;}

  .tbl-wrap{overflow-x:auto; margin-top:26px;}
  table{width:100%; border-collapse:collapse; font-size:13.5px;}
  th{text-align:right; font-family:'IBM Plex Mono', monospace; font-size:10.5px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-muted); font-weight:500; padding:8px 10px; border-bottom:1px solid var(--border);}
  th:first-child, td:first-child{text-align:left;}
  td{padding:10px; border-bottom:1px solid var(--border); text-align:right; font-variant-numeric:tabular-nums;}
  tr:last-child td{border-bottom:none;}
  .seg-swatch{display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:8px; vertical-align:middle;}

  .diag-grid{display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:24px;}
  @media (max-width:700px){ .diag-grid{grid-template-columns:1fr;} }
  .diag-card{background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px; box-shadow:var(--shadow);}
  .diag-card img{width:100%; border-radius:6px; display:block; background:#fff;}
  .diag-cap{font-size:12.5px; color:var(--ink-muted); margin-top:10px;}

  .callout{border-radius:10px; padding:16px 18px; margin:18px 0; border:1px solid var(--border); background:var(--accent-soft); border-color:color-mix(in srgb, var(--accent) 40%, var(--border));}
  .callout .label{font-family:'IBM Plex Mono', monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.07em; display:block; margin-bottom:6px; color:var(--accent);}
  .callout p{margin:0; max-width:none; color:var(--ink);}

  footer{margin-top:60px; padding-top:20px; border-top:1px solid var(--border); color:var(--ink-soft); font-size:12.5px; font-family:'IBM Plex Mono', monospace;}
  footer a{color:var(--ink-soft);}
</style>
</head>
<body>
<div class="shell">
  <header class="cover">
    <div class="eyebrow">Relatório de execução · FoCVS</div>
    <h1>__TOP_SEGMENT_PCT__ do valor futuro concentrado no topo dos __N_SEGMENTS__ segmentos</h1>
    <p class="subtitle">Resultado do pipeline sobre a base enviada nesta execução.</p>
    <div class="meta-panel">__META_ROWS__</div>
  </header>

  <section>
    <div class="kicker">Resumo da execução</div>
    <div class="kpi-grid">
      <div class="kpi"><div class="v">__KPI_CUSTOMERS__</div><div class="l">Clientes modelados</div></div>
      <div class="kpi"><div class="v">__KPI_TRANSACTIONS__</div><div class="l">Transações observadas</div></div>
      <div class="kpi"><div class="v __KPI_MAPE_CLASS__">__KPI_MAPE__</div><div class="l">Erro de validação (MAPE)</div></div>
      <div class="kpi"><div class="v">__KPI_HORIZON__</div><div class="l">Horizonte de previsão</div></div>
    </div>
  </section>

  <section>
    <div class="kicker">Segmentação por valor futuro</div>
    <h2>Concentração de valor por segmento</h2>
    <p class="lede">Modelo __KPI_MODEL__, granularidade __KPI_GRANULARITY__. Cada cliente foi colocado num dos __N_SEGMENTS__ segmentos pelo CLV previsto.</p>
    <div class="chart-card">
      <div class="chart-title">% do valor futuro total, por segmento</div>
      <div class="chart-note">Passe o mouse sobre uma barra para ver o valor médio previsto por cliente</div>
      <div class="bars-pct" id="segChart">__SEGMENT_BARS__
      </div>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr><th>Segmento</th><th>Clientes</th><th>Retenção média</th><th>Valor médio previsto</th><th>Ticket médio previsto</th><th>% do valor total</th></tr>
        </thead>
        <tbody>__SEGMENT_TABLE_ROWS__
        </tbody>
      </table>
    </div>
  </section>
__EXTRA_DIMENSION_SECTION__
__DIAGNOSTIC_SECTION__

  <footer>Gerado automaticamente por webapp/report.py a partir da saída de fcvs_pipeline_csv.py · __GENERATED_AT__</footer>
</div>

<div class="tooltip" id="tip"></div>
<script>
  const tip = document.getElementById('tip');
  document.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('mouseenter', () => { tip.innerHTML = el.dataset.tip; tip.classList.add('show'); });
    el.addEventListener('mousemove', (e) => { tip.style.left = e.clientX + 'px'; tip.style.top = (e.clientY - 14) + 'px'; });
    el.addEventListener('mouseleave', () => { tip.classList.remove('show'); });
  });
</script>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output_folder', required=True,
                         help='Folder containing the pipeline output files.')
    parser.add_argument('--run_name', default=None,
                         help='Display name for this run (default: folder name).')
    args = parser.parse_args()
    path = generate(args.output_folder, args.run_name)
    print(f'Report written to {path}')


if __name__ == '__main__':
    main()
