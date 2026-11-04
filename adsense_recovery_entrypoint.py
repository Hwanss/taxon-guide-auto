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
    editorial_freeze = os.getenv("ADSENSE_EDITORIAL_FREEZE", "false").lower() == "true"

    if phase == "readiness":
        return run("AdSense 최종 준비도 검사", "adsense_readiness_v63.py", "--strict")

    if phase == "status_only":
        return run("파이프라인 상태 확인", "pipeline_controller.py")

    if phase == "auto_publish":
        if editorial_freeze:
            print("⏸️ AdSense 재심사 전 편집 검수 동결: 자동공개 금지", flush=True)
            return 0
        return run("v6.4.1 엄격 자동 최종검수/조건부 공개", "adsense_auto_publish_v641.py")

    if editorial_freeze and phase in {"auto", "cleanup"}:
        print("⏸️ 편집 검수 동결: 자동 생성·재작성·공개를 중단하고 공개 사이트 검사만 수행합니다.", flush=True)
        pipeline_code = 0
    else:
        pipeline_code = run("기존 AdSense 복구 파이프라인", "pipeline_controller.py")

    if phase not in {"auto", "cleanup"}:
        return pipeline_code

    # v6.4.3 fail-safe: a transient content-processing failure must not prevent
    # Public Guard / Readiness from checking the live public site.
    if pipeline_code != 0:
        print(
            "⚠️ 콘텐츠 복구 파이프라인이 실패했지만 공개 사이트 안전검사를 계속합니다.",
            flush=True,
        )

    guard_code = run("공개 글 AdSense 하드블로커 가드", "adsense_public_guard_v63.py")

    auto_publish_code = 0
    if pipeline_code == 0 and guard_code == 0 and not editorial_freeze:
        auto_publish_code = run(
            "v6.4.1 엄격 자동 최종검수/조건부 공개",
            "adsense_auto_publish_v641.py",
        )
    else:
        print(
            "⏭️ 선행 단계 오류가 있어 이번 실행의 자동공개 단계는 건너뜁니다.",
            flush=True,
        )

    # Readiness is always executed last, even if cleanup/WordPress work failed.
    report_code = run("AdSense 준비도 스냅샷", "adsense_readiness_v63.py")
    if report_code != 0:
        print(
            "⚠️ 준비도 스냅샷 검사 자체에 오류가 있거나 NOT READY 상태입니다.",
            flush=True,
        )

    # Preserve failure visibility in GitHub Actions while still producing the
    # public-safety/readiness reports needed during AdSense review.
    for code in (pipeline_code, guard_code, auto_publish_code, report_code):
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
