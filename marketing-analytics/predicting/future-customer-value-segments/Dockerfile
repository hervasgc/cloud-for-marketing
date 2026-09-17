# Container for the FoCVS web UI (webapp/) + pipeline (fcvs_pipeline_csv.py),
# built for Cloud Run. Unlike a Mac on Apple Silicon, linux/amd64 has an
# official prebuilt wheel for apache-beam==2.60.0, so no source build is
# needed here -- pip just downloads it.
FROM python:3.11-slim

WORKDIR /app

# Pipeline dependencies first (hash-locked, rarely change) so Docker can
# cache this layer across rebuilds of the application code below.
COPY requirements_local.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements_local.txt

COPY webapp/requirements_webapp.txt webapp/requirements_webapp.txt
RUN pip install --no-cache-dir -r webapp/requirements_webapp.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# --chdir webapp makes `import report` inside app.py resolve the same way it
# does when run locally with `python webapp/app.py` (module lookup relative
# to the current working directory).
# --timeout 0 disables gunicorn's own worker timeout: the real ceiling on how
# long a run may take is PIPELINE_TIMEOUT_SECONDS in app.py plus Cloud Run's
# own request timeout (set to 3600s in the deploy script).
CMD exec gunicorn --chdir webapp --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 app:app
