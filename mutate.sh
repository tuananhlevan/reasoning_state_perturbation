#!/usr/bin/env bash
set -euo pipefail
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh"
conda activate mutate

python3 src/authenticate.py
python3 src/mutate.py 'https://drive.google.com/drive/folders/1fkSXw03MJEU_1Hs2uRZKDi2b8_KBGVgL' --workers "${WORKERS:-1}"
