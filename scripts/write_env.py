"""Generates the repo-root .env file from OpenTofu outputs.

Run after `tofu apply` succeeds:

    python scripts/write_env.py
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = REPO_ROOT / "infra"
ENV_PATH = REPO_ROOT / ".env"


def main() -> None:
    result = subprocess.run(
        ["tofu", "output", "-json"],
        cwd=INFRA_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit("tofu output failed - did you run `tofu apply` in infra/ first?")

    outputs = {k: v["value"] for k, v in json.loads(result.stdout).items()}

    lines = [
        f"COSMOS_ENDPOINT={outputs['cosmos_endpoint']}",
        f"COSMOS_KEY={outputs['cosmos_key']}",
        f"COSMOS_DATABASE={outputs['cosmos_database']}",
        f"COSMOS_CONTAINER={outputs['cosmos_container']}",
        "",
        f"AZURE_VISION_ENDPOINT={outputs['vision_endpoint']}",
        f"AZURE_VISION_KEY={outputs['vision_key']}",
        f"AZURE_VISION_MODEL_VERSION={outputs['vision_model_version']}",
        "",
        f"AZURE_OPENAI_ENDPOINT={outputs['openai_endpoint']}",
        f"AZURE_OPENAI_KEY={outputs['openai_key']}",
        f"AZURE_OPENAI_DEPLOYMENT={outputs['openai_deployment']}",
        "",
        f"BLOB_ACCOUNT_NAME={outputs['blob_account_name']}",
        f"BLOB_ACCOUNT_KEY={outputs['blob_account_key']}",
        f"BLOB_CONTAINER={outputs['blob_container']}",
        "",
    ]

    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {ENV_PATH}")


if __name__ == "__main__":
    main()
