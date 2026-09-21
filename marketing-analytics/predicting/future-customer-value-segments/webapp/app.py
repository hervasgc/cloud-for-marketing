#!/usr/bin/env python3
"""Local web UI for running the FoCVS pipeline against an uploaded CSV.

Flow:
  1. GET  /            -> upload form (run name + CSV file)
  2. POST /upload       -> saves the file, reads its header, shows the
                           column-mapping + parameters form
  3. POST /run          -> runs fcvs_pipeline_csv.py (DirectRunner) into
                           output/<run-name-slug>/ and generates report.html
  4. GET  /runs         -> list of past runs
  5. GET  /runs/<slug>  -> the generated report for that run

Every run's outputs live under output/<slug>/ (or wherever FOCVS_RUNS_DIR
points to -- e.g. a GCS volume mount on Cloud Run), named after the run name
the user typed -- this is the "one folder per execution" behavior the UI adds
on top of the plain CLI scripts (install.sh / run_locally.sh).

The pipeline itself always runs against local disk (FOCVS_WORK_DIR, fast and
POSIX-complete) and the finished run folder is then moved into FOCVS_RUNS_DIR
-- the persistent store, which can safely be a mounted network filesystem
such as a Cloud Storage volume.

Run locally with:
    source focvs-env/bin/activate
    python webapp/app.py

Environment variables (all optional, sensible local defaults):
    FOCVS_RUNS_DIR  Where finished runs are kept. Default: <repo>/output
    FOCVS_WORK_DIR  Scratch space the pipeline writes to while running.
                    Default: <repo>/.work
    PORT            Port to listen on when run directly (not via gunicorn).
                    Default: 5000
"""

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime

from flask import (Flask, redirect, render_template, request, send_file,
                    send_from_directory, url_for)

import report

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_STORE_DIR = os.environ.get('FOCVS_RUNS_DIR', os.path.join(BASE_DIR, 'output'))
WORK_ROOT = os.environ.get('FOCVS_WORK_DIR', os.path.join(BASE_DIR, '.work'))
PENDING_DIR = os.path.join(WORK_ROOT, '.pending')
PIPELINE_SCRIPT = os.path.join(BASE_DIR, 'fcvs_pipeline_csv.py')
PIPELINE_TIMEOUT_SECONDS = 3600

DOWNLOADABLE_FILES = (
    'input.csv', 'prediction_summary.csv',
    'prediction_summary_extra_dimension.csv', 'prediction_by_customer.csv',
    'prediction_params.txt', 'validation_params.txt', 'pipeline.log',
    'repeat_transactions_over_time.png', 'repeat_cumulative_transactions_over_time.png',
)

FREQUENCY_MODELS = [
    ('MBGNBD', 'MBG/NBD (recomendado)'),
    ('BGNBD', 'BG/NBD'),
    ('PNBD', 'Pareto/NBD'),
    ('BGBB', 'BG/BB (experimental)'),
]

GRANULARITIES = [
    ('weekly', 'Semanal'),
    ('daily', 'Diária'),
    ('monthly', 'Mensal'),
]

DATE_PATTERN_SUGGESTIONS = [
    'YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY/MM/DD', 'DD-MM-YYYY',
]

FIELD_GUESS_KEYWORDS = {
    'customer_id': ['customer', 'cliente', 'cpf', 'cust_id', 'customerid'],
    'transaction_date': ['date', 'data'],
    'sales': ['sales', 'valor', 'venda', 'amount', 'total', 'price', 'preco'],
    'extra_dimension': ['category', 'categoria', 'canal', 'channel', 'polo',
                         'dimension', 'segment', 'modalidade'],
}

os.makedirs(RUNS_STORE_DIR, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB


def slugify(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.strip().lower())
    return slug.strip('-')[:60]


def guess_column(headers, field):
    keywords = FIELD_GUESS_KEYWORDS.get(field, [])
    lower_headers = [h.lower() for h in headers]
    for kw in keywords:
        for i, h in enumerate(lower_headers):
            if kw in h:
                return i
    return None


def read_csv_header(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        first_line = f.readline()
    return next(csv.reader([first_line]))


def work_dir(slug):
    return os.path.join(WORK_ROOT, slug) + os.sep


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    run_name = request.form.get('run_name', '').strip()
    csv_file = request.files.get('csv_file')

    errors = []
    if not run_name:
        errors.append('Informe um nome para a execução.')
    slug = slugify(run_name) if run_name else ''
    if run_name and not slug:
        errors.append('O nome informado não gera um nome de pasta válido. Use letras, números ou espaços.')
    if slug and os.path.isdir(os.path.join(RUNS_STORE_DIR, slug)):
        errors.append(f'Já existe uma execução chamada "{run_name}". Escolha outro nome.')
    if not csv_file or not csv_file.filename:
        errors.append('Selecione um arquivo CSV.')

    if errors:
        return render_template('index.html', errors=errors, run_name=run_name)

    token = uuid.uuid4().hex
    pending_path = os.path.join(PENDING_DIR, token)
    os.makedirs(pending_path, exist_ok=True)
    saved_csv_path = os.path.join(pending_path, 'input.csv')
    csv_file.save(saved_csv_path)

    try:
        headers = read_csv_header(saved_csv_path)
    except (OSError, StopIteration, csv.Error):
        shutil.rmtree(pending_path, ignore_errors=True)
        return render_template(
            'index.html', run_name=run_name,
            errors=['Não foi possível ler o cabeçalho do CSV enviado. Confira o arquivo e tente novamente.'])

    guesses = {field: guess_column(headers, field) for field in FIELD_GUESS_KEYWORDS}

    return render_template(
        'mapping.html',
        token=token,
        run_name=run_name,
        source_filename=csv_file.filename,
        headers=list(enumerate(headers)),
        guesses=guesses,
        frequency_models=FREQUENCY_MODELS,
        granularities=GRANULARITIES,
        date_pattern_suggestions=DATE_PATTERN_SUGGESTIONS,
    )


@app.route('/run', methods=['POST'])
def run_pipeline():
    form = request.form
    token = form.get('token', '')
    run_name = form.get('run_name', '').strip()
    source_filename = form.get('source_filename', '')
    slug = slugify(run_name)

    pending_csv = os.path.join(PENDING_DIR, token, 'input.csv')
    if not slug or not os.path.isfile(pending_csv):
        return render_template(
            'index.html',
            errors=['A sessão de upload expirou ou é inválida. Envie o arquivo novamente.'])
    if os.path.isdir(os.path.join(RUNS_STORE_DIR, slug)):
        return render_template(
            'index.html', run_name=run_name,
            errors=[f'Já existe uma execução chamada "{run_name}". Escolha outro nome.'])

    # The pipeline always writes to local scratch space first -- fast, full
    # POSIX semantics -- and the finished folder is moved into the durable
    # store (RUNS_STORE_DIR) only once the run is done. This is what lets
    # RUNS_STORE_DIR safely be a mounted Cloud Storage volume on Cloud Run.
    target_dir = work_dir(slug)
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)
    final_csv = target_dir + 'input.csv'
    shutil.move(pending_csv, final_csv)
    shutil.rmtree(os.path.join(PENDING_DIR, token), ignore_errors=True)

    headers = read_csv_header(final_csv)

    def col_position(field_name):
        raw = form.get(field_name, '')
        if raw == '' or raw == 'none':
            return None
        return int(raw) + 1  # pipeline positions are 1-indexed

    customer_pos = col_position('customer_id_column')
    date_pos = col_position('transaction_date_column')
    sales_pos = col_position('sales_column')
    extra_pos = col_position('extra_dimension_column')

    date_pattern = form.get('date_parsing_pattern') or 'YYYY-MM-DD'
    granularity = form.get('model_time_granularity') or 'weekly'
    frequency_model = form.get('frequency_model_type') or 'MBGNBD'
    prediction_period = form.get('prediction_period') or '52'
    output_segments = form.get('output_segments') or '5'
    mape_threshold = form.get('transaction_frequency_threshold') or '15'
    penalizer_coef = form.get('penalizer_coef') or '0.0'

    column_mapping = {
        'customer_id': headers[customer_pos - 1] if customer_pos else None,
        'transaction_date': headers[date_pos - 1] if date_pos else None,
        'sales': headers[sales_pos - 1] if sales_pos else None,
        'extra_dimension': headers[extra_pos - 1] if extra_pos else None,
    }

    run_meta = {
        'run_name': run_name,
        'slug': slug,
        'source_filename': source_filename,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'column_mapping': column_mapping,
        'date_parsing_pattern': date_pattern,
        'model_time_granularity': granularity,
        'frequency_model_type': frequency_model,
        'prediction_period': prediction_period,
        'output_segments': output_segments,
        'transaction_frequency_threshold': mape_threshold,
        'penalizer_coef': penalizer_coef,
    }
    with open(target_dir + 'run_meta.json', 'w', encoding='utf-8') as f:
        json.dump(run_meta, f, ensure_ascii=False, indent=2)

    args = [
        sys.executable, PIPELINE_SCRIPT,
        '--runner=DirectRunner',
        f'--input_csv={final_csv}',
        f'--output_folder={target_dir}',
        f'--customer_id_column_position={customer_pos}',
        f'--transaction_date_column_position={date_pos}',
        f'--sales_column_position={sales_pos}',
        f'--date_parsing_pattern={date_pattern}',
        f'--model_time_granularity={granularity}',
        f'--frequency_model_type={frequency_model}',
        f'--prediction_period={prediction_period}',
        f'--output_segments={output_segments}',
        f'--transaction_frequency_threshold={mape_threshold}',
        f'--penalizer_coef={penalizer_coef}',
    ]
    if extra_pos:
        args.append(f'--extra_dimension_column_position={extra_pos}')

    try:
        result = subprocess.run(
            args, cwd=BASE_DIR, capture_output=True, text=True,
            timeout=PIPELINE_TIMEOUT_SECONDS)
        log_text = result.stdout + '\n' + result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as e:
        log_text = (e.stdout or '') + '\n' + (e.stderr or '') + \
            '\n\nExecução interrompida: passou de ' \
            f'{PIPELINE_TIMEOUT_SECONDS // 60} minutos.'
        returncode = -1

    with open(target_dir + 'pipeline.log', 'w', encoding='utf-8') as f:
        f.write(log_text)

    if returncode != 0:
        hint = None
        if 'MAPE' in log_text or 'Mean Absolute Percent Error' in log_text:
            hint = ('O modelo não passou na validação automática (erro acima '
                     'do limite configurado). Tente ajustar o coeficiente de '
                     'penalização ou o limite de MAPE, ou revisar o '
                     'mapeamento de colunas.')
        shutil.move(target_dir.rstrip(os.sep), os.path.join(RUNS_STORE_DIR, slug))
        return render_template(
            'error.html', run_name=run_name, slug=slug,
            log_tail=log_text[-6000:], hint=hint)

    report.generate(target_dir, run_name, slug=slug)
    shutil.move(target_dir.rstrip(os.sep), os.path.join(RUNS_STORE_DIR, slug))
    return redirect(url_for('view_run', slug=slug))


@app.route('/runs')
def list_runs():
    runs = []
    if os.path.isdir(RUNS_STORE_DIR):
        for entry in sorted(os.listdir(RUNS_STORE_DIR)):
            if entry.startswith('.'):
                continue
            full = os.path.join(RUNS_STORE_DIR, entry)
            if not os.path.isdir(full):
                continue
            meta_path = os.path.join(full, 'run_meta.json')
            display_name = entry
            created_at = datetime.fromtimestamp(os.path.getmtime(full)).strftime('%d/%m/%Y %H:%M')
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, encoding='utf-8') as f:
                        meta = json.load(f)
                    display_name = meta.get('run_name', entry)
                except (json.JSONDecodeError, OSError):
                    pass
            if os.path.isfile(os.path.join(full, 'report.html')):
                status = 'ok'
            elif os.path.isfile(os.path.join(full, 'pipeline.log')):
                status = 'failed'
            else:
                status = 'unknown'
            runs.append({
                'slug': entry, 'name': display_name,
                'created_at': created_at, 'status': status,
            })
    runs.sort(key=lambda r: r['created_at'], reverse=True)
    return render_template('runs.html', runs=runs)


@app.route('/runs/<slug>')
def view_run(slug):
    report_path = os.path.join(RUNS_STORE_DIR, slug, 'report.html')
    if os.path.isfile(report_path):
        return send_file(report_path)
    log_path = os.path.join(RUNS_STORE_DIR, slug, 'pipeline.log')
    if os.path.isfile(log_path):
        with open(log_path, encoding='utf-8') as f:
            log_text = f.read()
        return render_template('error.html', run_name=slug, slug=slug,
                                log_tail=log_text[-6000:], hint=None)
    return ('Execução não encontrada.', 404)


@app.route('/runs/<slug>/download/<fname>')
def download_run_file(slug, fname):
    if fname not in DOWNLOADABLE_FILES:
        return ('Arquivo não disponível para download.', 404)
    folder = os.path.join(RUNS_STORE_DIR, slug)
    if not os.path.isfile(os.path.join(folder, fname)):
        return ('Arquivo não encontrado.', 404)
    return send_from_directory(folder, fname, as_attachment=True)


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    print(f'FoCVS local UI em http://{host}:{port}')
    app.run(host=host, port=port, debug=False, threaded=True)
