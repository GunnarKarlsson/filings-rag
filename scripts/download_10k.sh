#!/usr/bin/env bash
# One-shot bootstrap: fetch provided 10-K HTML URLs into data/10k/.
# Not part of the app CLI — run once (or again after editing the company list).
set -euo pipefail

PROJECT_ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPANY_LIST="${1:-$PROJECT_ROOT_DIR/companies/initial_company_list.txt}"
DESTINATION_DIR="$PROJECT_ROOT_DIR/data/10k"
# SEC fair-access: identify the project and include a contact email.
USER_AGENT="FilingsRAG research filings-rag@example.com"

if [[ ! -f "$COMPANY_LIST" ]]; then
  echo "Company list not found: $COMPANY_LIST" >&2
  exit 1
fi

mkdir -p "$DESTINATION_DIR"

sanitize_key() {
  local raw="$1"
  # Strip leading #/whitespace, trailing : or ;, whitespace
  raw="$(echo "$raw" | sed -E 's/^[[:space:]]*#?[[:space:]]*//; s/[[:space:]]*[:;][[:space:]]*$//; s/^[[:space:]]+//; s/[[:space:]]+$//')"
  # Path-safe: slashes and spaces → underscore
  echo "$raw" | tr '/ ' '_' | tr -cd '[:alnum:]_-' | tr '[:upper:]' '[:lower:]'
}

company_key=""
count=0

while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip blank lines
  if [[ -z "${line//[[:space:]]/}" ]]; then
    continue
  fi

  # Label line: "nvidia:", "# apple:", "amazon;", "# google/alphabet:"
  if [[ "$line" =~ ^[[:space:]]*#?[[:space:]]*[^[:space:]#].*[:\;][[:space:]]*$ ]]; then
    company_key="$(sanitize_key "$line")"
    if [[ -z "$company_key" ]]; then
      echo "Could not parse company label: $line" >&2
      exit 1
    fi
    continue
  fi

  # URL line
  if [[ "$line" =~ ^[[:space:]]*https:// ]]; then
    url="$(echo "$line" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
    if [[ -z "$company_key" ]]; then
      echo "URL without preceding company label: $url" >&2
      exit 1
    fi

    # .../data/{cik}/{accession}/{filename}
    if [[ ! "$url" =~ /Archives/edgar/data/([^/]+)/([^/]+)/([^/]+)$ ]]; then
      echo "Unrecognized EDGAR URL shape: $url" >&2
      exit 1
    fi
    cik="${BASH_REMATCH[1]}"
    accession="${BASH_REMATCH[2]}"
    primary_document="${BASH_REMATCH[3]}"

    dest_dir="$DESTINATION_DIR/$company_key/$accession"
    dest_htm="$dest_dir/10k.htm"
    dest_meta="$dest_dir/meta.json"
    mkdir -p "$dest_dir"

    echo "Fetching $company_key ← $url"
    curl -fsSL \
      -A "$USER_AGENT" \
      -o "$dest_htm" \
      "$url"

    # Reject empty / obvious error pages
    size="$(wc -c < "$dest_htm" | tr -d ' ')"
    if [[ "$size" -lt 10000 ]]; then
      echo "Download looks too small (${size} bytes) for $company_key — check User-Agent / URL" >&2
      exit 1
    fi

    cat > "$dest_meta" <<EOF
{
  "company_key": "$company_key",
  "cik": "$cik",
  "accession": "$accession",
  "primary_document": "$primary_document",
  "sec_url": "$url"
}
EOF

    echo "  → $dest_htm ($size bytes)"
    count=$((count + 1))
    company_key=""
    # Be polite to EDGAR
    sleep 0.5
    continue
  fi

  echo "Skipping unrecognized line: $line" >&2
done < "$COMPANY_LIST"

if [[ "$count" -eq 0 ]]; then
  echo "No filings downloaded from $COMPANY_LIST" >&2
  exit 1
fi

echo "Done. Downloaded $count filing(s) under $DESTINATION_DIR"
