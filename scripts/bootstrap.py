"""Generate local secrets and start this project's Compose stack without printing credentials."""

import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = ROOT / ".env"
    if not env.exists():
        env.write_text(
            "\n".join(
                [
                    f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}",
                    f"BOREAL_RUNTIME_PASSWORD={secrets.token_urlsafe(32)}",
                    f"BOREAL_MIGRATION_PASSWORD={secrets.token_urlsafe(32)}",
                    "BOREAL_ORIGIN=http://127.0.0.1:8000",
                    "BOREAL_DEMO=1",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        env.chmod(0o600)
    (ROOT / ".local").mkdir(exist_ok=True)
    subprocess.run(["docker", "compose", "up", "--build", "-d", "--wait"], cwd=ROOT, check=True)
    subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "scripts/seed.py"], cwd=ROOT, check=True)
    subprocess.run(
        ["docker", "compose", "cp", "api:/app/.local/accounts.json", ".local/accounts.json"], cwd=ROOT, check=True
    )
    (ROOT / ".local" / "accounts.json").chmod(0o600)
    print("BOREAL: http://127.0.0.1:8000")
    print("Generated credentials: .local/accounts.json (keep private).")


if __name__ == "__main__":
    main()
