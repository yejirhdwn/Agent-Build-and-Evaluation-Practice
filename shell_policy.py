"""에이전트 셸(execute) 허용 목록.

``virtual_mode=True`` 는 파일 도구(read_file/ls/grep 등)의 경로만 workspace 로 묶는다.
``execute`` 는 ``shell=True`` 로 호스트에서 그대로 실행되므로 ``cat ../eval/answer_keys/S1.md``
같은 명령으로 정답 파일을 읽을 수 있다. 그래서 셸 명령은 아래 허용 목록에 맞을 때만 실행한다.

- 기본: ``date`` 만 허용한다(시각 확인용). ``-f``/``-r`` 처럼 파일을 읽는 옵션은 막는다.
- ``META_HARNESS_ENABLED=1`` 일 때만 meta-harness CLI(``python skills/meta-harness/metaharness.py``)를
  추가로 허용한다. 평가(S1~S4) 중에는 켜지 않는다.

셸 메타문자(``; & | < > $ ` \\``, 개행)가 들어간 명령은 모두 거부한다. 따라서 허용된 명령
뒤에 다른 명령을 이어 붙이거나 치환·리다이렉션으로 우회할 수 없다.
"""

from __future__ import annotations

import os
import re
import shlex

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse

_FORBIDDEN_CHARS = set(";&|<>$`\\\n\r")
_ENV_ASSIGN = re.compile(r"^TZ=[A-Za-z0-9_+\-/]+$")
_DATE_FORMAT = re.compile(r"^\+[%A-Za-z0-9:_\-./ ]*$")
_DATE_FLAGS = {"-u", "--utc", "--universal", "-R", "--rfc-email", "-I"}
_DATE_FLAG_PREFIXES = ("-I", "--iso-8601", "--rfc-3339=")
_PYTHON = {"python", "python3"}
_META_HARNESS_SCRIPT = "skills/meta-harness/metaharness.py"


def meta_harness_enabled() -> bool:
    return os.getenv("META_HARNESS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_allowed_date(args: list[str]) -> bool:
    for arg in args:
        if arg in _DATE_FLAGS or _DATE_FORMAT.match(arg):
            continue
        if arg.startswith(_DATE_FLAG_PREFIXES) and re.match(r"^[-A-Za-z0-9=]+$", arg):
            continue
        return False
    return True


def _is_allowed_meta_harness(argv: list[str]) -> bool:
    if argv[:2] == ["uv", "run"]:
        argv = argv[2:]
    return (
        len(argv) >= 2
        and argv[0] in _PYTHON
        and argv[1].lstrip("./") == _META_HARNESS_SCRIPT
    )


def check_command(command: str, *, allow_meta_harness: bool | None = None) -> str | None:
    """허용되면 None, 거부되면 그 이유를 반환한다."""
    if allow_meta_harness is None:
        allow_meta_harness = meta_harness_enabled()
    if any(ch in _FORBIDDEN_CHARS for ch in command):
        return "셸 메타문자(; & | < > $ ` \\ 또는 개행)는 사용할 수 없습니다."
    try:
        argv = shlex.split(command)
    except ValueError:
        return "명령을 해석할 수 없습니다."
    while argv and _ENV_ASSIGN.match(argv[0]):
        argv = argv[1:]
    if not argv:
        return "빈 명령입니다."
    if argv[0] == "date":
        return None if _is_allowed_date(argv[1:]) else "date 는 출력 형식(+FORMAT)과 -u/-I/-R 옵션만 쓸 수 있습니다."
    if allow_meta_harness and _is_allowed_meta_harness(argv):
        return None
    allowed = "date"
    if allow_meta_harness:
        allowed += f", python {_META_HARNESS_SCRIPT}"
    return f"허용되지 않은 명령입니다. 허용 목록: {allowed}. 파일은 파일 도구로, 데이터는 조회 도구로 확인하세요."


class RestrictedShellBackend(LocalShellBackend):
    """``execute`` 를 허용 목록으로 제한한 LocalShellBackend.

    ``aexecute`` 는 내부에서 ``execute`` 를 호출하므로 함께 제한된다.
    ``allow_meta_harness`` 를 주면 환경변수 대신 그 값으로 meta-harness CLI 허용 여부를 정한다
    (개선 에이전트 그래프는 True, 로그 추적 에이전트는 환경변수 기본값).
    """

    def __init__(self, *args, allow_meta_harness: bool | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._allow_meta_harness = allow_meta_harness

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        reason = check_command(command, allow_meta_harness=self._allow_meta_harness)
        if reason:
            return ExecuteResponse(output=f"[거부됨] {reason}", exit_code=126)
        if timeout is None:
            return super().execute(command)
        return super().execute(command, timeout=timeout)
