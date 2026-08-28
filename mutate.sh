#!/usr/bin/env bash
set -euo pipefail
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh"
conda activate mutate

python3 src/authenticate.py

INPUT_FOLDER='https://drive.google.com/drive/folders/1Qy1xSCtwQvO-5LBru36lixLZU8zlyiOH'
OUTPUT_FOLDER='https://drive.google.com/drive/folders/1NrwjxBunPMtiK8Z-v1Lh40ctdmEymrtF'
UPLOAD_FLAG=--no-upload
USE_CACHE=--use-cache
FILL_CACHE=
if [[ "${UPLOAD:-1}" == "0" ]]; then UPLOAD_FLAG=--no-upload; fi
python3 src/mutate.py "$INPUT_FOLDER" "$OUTPUT_FOLDER" --workers 8 "$UPLOAD_FLAG" $USE_CACHE $FILL_CACHE --drive-timeout 120 --timeout 300
