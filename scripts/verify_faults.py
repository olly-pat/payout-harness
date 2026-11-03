#!/usr/bin/env python3
"""Fault drills: prove the suite fails when the service is broken.

For each known fault the service can be told to reintroduce, run the whole
suite and require it to fail. A suite that passes against a broken service is
not protecting anything, and this script is what keeps that honest.

    python scripts/verify_faults.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.faults import KNOWN  # noqa: E402

FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


def run(fault: str) -> tuple[int, list[str]]:
    env = dict(os.environ, PAYOUT_FAULTS=fault)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", "-rf"],
        env=env, capture_output=True, text=True,
    )
    return result.returncode, FAILED.findall(result.stdout)


def main() -> int:
    undetected = []
    for fault, description in sorted(KNOWN.items()):
        code, failures = run(fault)
        if code == 0:
            print(f"MISSED  {fault}: {description}")
            print("        the suite passed against a broken service")
            undetected.append(fault)
            continue
        print(f"CAUGHT  {fault}: {description}")
        for test in failures[:4]:
            print(f"        {test}")
        if len(failures) > 4:
            print(f"        and {len(failures) - 4} more")

    if undetected:
        print(f"\n{len(undetected)} fault(s) went undetected: {', '.join(undetected)}")
        return 1
    print(f"\nall {len(KNOWN)} faults were caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
