import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = PROJECT_ROOT / "reports" / "hw03"
RAW_DIR = REPORT_DIR / "raw"
OUTPUT_FILE = REPORT_DIR / "verification.json"

BASE_URL = "http://127.0.0.1:8509"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_url(path, expected_status):
    opener = build_opener(NoRedirect)

    request = Request(BASE_URL + path, method="GET")

    try:
        response = opener.open(request, timeout=10)
        status = response.status
        location = response.headers.get("Location")
    except HTTPError as error:
        status = error.code
        location = error.headers.get("Location")
    except (URLError, TimeoutError) as error:
        return {
            "check": f"GET {path}",
            "pass": False,
            "details": str(error),
        }

    passed = status == expected_status

    if path == "/dashboard":
        passed = passed and location == "/login"

    return {
        "check": f"GET {path}",
        "pass": passed,
        "details": {
            "status": status,
            "location": location,
        },
    }


def main():
    checks = []

    checks.append(check_url("/", 200))
    checks.append(check_url("/login", 200))
    checks.append(check_url("/dashboard", 303))

    raw_files = sorted(RAW_DIR.glob("*.json"))

    raw_file_check = {
        "check": "Exactly 15 raw retrieval JSON files exist",
        "pass": len(raw_files) == 15,
        "details": f"Found {len(raw_files)} raw JSON files",
    }
    checks.append(raw_file_check)

    required_fields = {
        "technique",
        "query_id",
        "query",
        "query_embedding_dimension",
        "query_embedding_first_8",
        "query_vector_shape",
        "document_vector_shape",
        "retrieval_latency_ms",
        "results",
    }

    valid_raw_files = 0

    for file_path in raw_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))

            if required_fields.issubset(data.keys()):
                valid_raw_files += 1

        except json.JSONDecodeError:
            pass

    raw_structure_check = {
        "check": "All raw files contain required retrieval fields",
        "pass": len(raw_files) == 15 and valid_raw_files == 15,
        "details": f"{valid_raw_files} of {len(raw_files)} files passed",
    }
    checks.append(raw_structure_check)

    required_files = [
        REPORT_DIR / "RUN_LOG.txt",
        REPORT_DIR / "METRICS.md",
        REPORT_DIR / "SOURCES.md",
        REPORT_DIR / "CORPUS_MANIFEST.json",
        REPORT_DIR / "questions.yaml",
    ]

    missing_files = [
        str(path.relative_to(PROJECT_ROOT))
        for path in required_files
        if not path.exists()
    ]

    required_files_check = {
        "check": "Required HW3 metadata files exist",
        "pass": len(missing_files) == 0,
        "details": (
            "All required files exist"
            if not missing_files
            else f"Missing: {missing_files}"
        ),
    }
    checks.append(required_files_check)

    overall_pass = all(item["pass"] for item in checks)

    result = {
        "project": "DATA 260 HW3",
        "checks": checks,
        "overall_pass": overall_pass,
    }

    OUTPUT_FILE.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2))
    print(f"\nVerification written to: {OUTPUT_FILE}")

    if not overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()