from __future__ import annotations

import os
import subprocess
import sys


def run(label: str, script: str, *args: str) -> int:
    print(f"\n▶ {label}: python {script} {' '.join(args)}", flush=True)
    completed = subprocess.run([sys.executable, script, *args], check=False)
    return int(completed.returncode)


def main() -> int:
    phase = os.getenv("FORCE_PHASE", "auto").strip().lower()

    if phase == "readiness":
        return run("AdSense v6.3 최종 준비도 검사", "adsense_readiness_v63.py", "--strict")

    if phase == "status_only":
        return run("파이프라인 상태 확인", "pipeline_controller.py")

    code = run("기존 AdSense 복구 파이프라인", "pipeline_controller.py")
    if code != 0:
        return code

    if phase not in {"auto", "cleanup"}:
        return 0

    guard_code = run("공개 글 AdSense 하드블로커/사람검수 가드", "adsense_public_guard_v63.py")
    if guard_code != 0:
        return guard_code

    # Always create a current report, but do not fail ordinary scheduled cleanup runs.
    report_code = run("AdSense v6.3 준비도 스냅샷", "adsense_readiness_v63.py")
    if report_code != 0:
        print(
            "⚠️ 준비도 스냅샷은 NOT READY입니다. 자동 정리 중에는 정상일 수 있으며 "
            "최종 재심사 직전에는 force_phase=readiness로 엄격 검사합니다.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
