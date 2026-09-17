#!/usr/bin/env bash
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


RUN_NAME="${1:-sample-cdnow}"
OUTPUT_DIR="./output/${RUN_NAME}/"

if [ -d "${OUTPUT_DIR}" ]; then
  rm -fr "${OUTPUT_DIR}"
fi
mkdir -p "${OUTPUT_DIR}"

python fcvs_pipeline_csv.py --runner=DirectRunner \
  --input_csv ./samples/input_cdnow.csv \
  --output_folder "${OUTPUT_DIR}" \
  --customer_id_column_position 1 \
  --transaction_date_column_position 2 \
  --sales_column_position 4 \
  --date_parsing_pattern YYYY-MM-DD \
  --model_time_granularity weekly \
  --penalizer_coef 0.0 \
  --extra_dimension_column_position 3

python webapp/report.py --output_folder "${OUTPUT_DIR}" --run_name "${RUN_NAME}"
echo "Report: ${OUTPUT_DIR}report.html"
