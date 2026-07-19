#!/usr/bin/env bash
set -euo pipefail
dataset="${1:?usage: stage-dataset.sh ims|exathlon SOURCE STORAGE_ACCOUNT}"
source_dir="${2:?source directory required}"
account="${3:?storage account required}"
case "$dataset" in ims|exathlon) ;; *) echo 'dataset must be ims or exathlon' >&2; exit 2;; esac
test -d "$source_dir"
echo "Review datasets/${dataset^^}.md and source terms before upload."
python - "$dataset" "$source_dir" <<'PY'
import hashlib,json,pathlib,sys,datetime
dataset,root=sys.argv[1],pathlib.Path(sys.argv[2]).resolve()
out=root/f"dataset-manifest-{dataset}.json"
rows=[]
for path in sorted(p for p in root.rglob('*') if p.is_file() and p != out):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    rows.append({'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':h.hexdigest()})
out.write_text(json.dumps({'dataset':dataset,'created_at_utc':datetime.datetime.now(datetime.UTC).isoformat(),'files':rows},indent=2)+'\n')
PY
az storage blob upload-batch --account-name "$account" --auth-mode login --destination datasets --destination-path "$dataset" --source "$source_dir" --overwrite false

