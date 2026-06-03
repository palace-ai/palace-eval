"""Verify: run tests and grade the agent's fix.

Self-contained — no external dependencies beyond stdlib.
Parser logic and grading extracted from swebench package at tasklist generation time.
"""

import re

# --- Constants ---

START_TEST_OUTPUT = ">>>>> Start Test Output"
END_TEST_OUTPUT = ">>>>> End Test Output"

# TestStatus values
PASSED = "PASSED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"
ERROR = "ERROR"
XFAIL = "XFAIL"
ALL_STATUSES = [FAILED, PASSED, SKIPPED, ERROR, XFAIL]


# --- Parsers ---

def parse_log_pytest(log):
    test_status_map = {}
    for line in log.split("\n"):
        if any(line.startswith(s) for s in ALL_STATUSES):
            if line.startswith(FAILED):
                line = line.replace(" - ", " ")
            test_case = line.split()
            if len(test_case) <= 1:
                continue
            test_status_map[test_case[1]] = test_case[0]
    return test_status_map


def parse_log_pytest_v2(log):
    test_status_map = {}
    escapes = "".join([chr(char) for char in range(1, 32)])
    for line in log.split("\n"):
        line = re.sub(r"\[(\d+)m", "", line)
        translator = str.maketrans("", "", escapes)
        line = line.translate(translator)
        if any(line.startswith(s) for s in ALL_STATUSES):
            if line.startswith(FAILED):
                line = line.replace(" - ", " ")
            test_case = line.split()
            if len(test_case) >= 2:
                test_status_map[test_case[1]] = test_case[0]
        elif any(line.endswith(s) for s in ALL_STATUSES):
            test_case = line.split()
            if len(test_case) >= 2:
                test_status_map[test_case[0]] = test_case[1]
    return test_status_map


def parse_log_pytest_options(log):
    option_pattern = re.compile(r"(.*?)\[(.*)\]")
    test_status_map = {}
    for line in log.split("\n"):
        if any(line.startswith(s) for s in ALL_STATUSES):
            if line.startswith(FAILED):
                line = line.replace(" - ", " ")
            test_case = line.split()
            if len(test_case) <= 1:
                continue
            has_option = option_pattern.search(test_case[1])
            if has_option:
                main, option = has_option.groups()
                if option.startswith("/") and not option.startswith("//") and "*" not in option:
                    option = "/" + option.split("/")[-1]
                test_name = f"{main}[{option}]"
            else:
                test_name = test_case[1]
            test_status_map[test_name] = test_case[0]
    return test_status_map


def parse_log_django(log):
    test_status_map = {}
    prev_test = None
    for line in log.split("\n"):
        line = line.strip()
        if "--version is equivalent to version" in line:
            test_status_map["--version is equivalent to version"] = PASSED
        if " ... " in line:
            prev_test = line.split(" ... ")[0]
        pass_suffixes = (" ... ok", " ... OK", " ...  OK")
        for suffix in pass_suffixes:
            if line.endswith(suffix):
                if line.strip().startswith("Applying sites.0002_alter_domain_unique...test_no_migrations"):
                    line = line.split("...", 1)[-1].strip()
                test = line.rsplit(suffix, 1)[0]
                test_status_map[test] = PASSED
                break
        if " ... skipped" in line:
            test_status_map[line.split(" ... skipped")[0]] = SKIPPED
        if line.endswith(" ... FAIL"):
            test_status_map[line.split(" ... FAIL")[0]] = FAILED
        if line.startswith("FAIL:"):
            test_status_map[line.split()[1].strip()] = FAILED
        if line.endswith(" ... ERROR"):
            test_status_map[line.split(" ... ERROR")[0]] = ERROR
        if line.startswith("ERROR:"):
            test_status_map[line.split()[1].strip()] = ERROR
        if line.lstrip().startswith("ok") and prev_test is not None:
            test_status_map[prev_test] = PASSED
    # Handle multiline django test output bugs
    patterns = [
        r"^(.*?)\s\.\.\.\sTesting\ against\ Django\ installed\ in\ ((?s:.*?))\ silenced\)\.\nok$",
        r"^(.*?)\s\.\.\.\sInternal\ Server\ Error:\ \/(.*)\\/\nok$",
        r"^(.*?)\s\.\.\.\sSystem check identified no issues \(0 silenced\)\nok$",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, log, re.MULTILINE):
            test_status_map[match.group(1)] = PASSED
    return test_status_map


def parse_log_matplotlib(log):
    test_status_map = {}
    for line in log.split("\n"):
        line = line.replace("MouseButton.LEFT", "1").replace("MouseButton.RIGHT", "3")
        if any(line.startswith(s) for s in ALL_STATUSES):
            if line.startswith(FAILED):
                line = line.replace(" - ", " ")
            test_case = line.split()
            if len(test_case) <= 1:
                continue
            test_status_map[test_case[1]] = test_case[0]
    return test_status_map


def parse_log_seaborn(log):
    test_status_map = {}
    for line in log.split("\n"):
        if line.startswith(FAILED):
            test_status_map[line.split()[1]] = FAILED
        elif f" {PASSED} " in line:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == PASSED:
                test_status_map[parts[0]] = PASSED
        elif line.startswith(PASSED):
            parts = line.split()
            if len(parts) >= 2:
                test_status_map[parts[1]] = PASSED
    return test_status_map


def parse_log_sympy(log):
    test_status_map = {}
    pattern = r"(_*) (.*)\.py:(.*) (_*)"
    for match in re.findall(pattern, log):
        test_status_map[f"{match[1]}.py:{match[2]}"] = FAILED
    for line in log.split("\n"):
        line = line.strip()
        if line.startswith("test_"):
            if line.endswith(" E"):
                test_status_map[line.split()[0]] = ERROR
            elif line.endswith(" F"):
                test_status_map[line.split()[0]] = FAILED
            elif line.endswith(" ok"):
                test_status_map[line.split()[0]] = PASSED
    return test_status_map


# Repo → parser mapping (embedded at generation time)
REPO_TO_PARSER = {
    "astropy/astropy": parse_log_pytest_v2,
    "django/django": parse_log_django,
    "matplotlib/matplotlib": parse_log_matplotlib,
    "mwaskom/seaborn": parse_log_seaborn,
    "pallets/flask": parse_log_pytest,
    "psf/requests": parse_log_pytest_options,
    "pydata/xarray": parse_log_pytest,
    "pylint-dev/pylint": parse_log_pytest_options,
    "pytest-dev/pytest": parse_log_pytest,
    "scikit-learn/scikit-learn": parse_log_pytest_v2,
    "sphinx-doc/sphinx": parse_log_pytest_v2,
    "sympy/sympy": parse_log_sympy,
}


# --- Grading ---

def grade(test_results, fail_to_pass, pass_to_pass):
    """Grade based on swebench criteria: all F2P must pass, all P2P must still pass."""
    f2p_passed = all(
        test_results.get(t) in (PASSED, XFAIL) for t in fail_to_pass
    )
    p2p_passed = all(
        test_results.get(t) in (PASSED, XFAIL) for t in pass_to_pass
    ) if pass_to_pass else True

    if f2p_passed and p2p_passed:
        return "FULL"
    elif any(test_results.get(t) in (PASSED, XFAIL) for t in fail_to_pass) and p2p_passed:
        return "PARTIAL"
    return "NO"


# --- Main verify function ---

async def verify(expected_outcome, agent_answer, ctx):
    """Execute eval script, parse test output, grade pass/fail."""
    eval_script = expected_outcome["eval_script"]
    repo = expected_outcome["repo"]
    fail_to_pass = expected_outcome["fail_to_pass"]
    pass_to_pass = expected_outcome["pass_to_pass"]

    # Write and execute eval script
    await ctx.write("/tmp/eval.sh", eval_script.encode())
    exit_code, output = await ctx.exec("bash /tmp/eval.sh", timeout=600)

    # Extract test output between markers
    test_output = _extract_between_markers(output)
    if not test_output:
        reason = "Eval script crashed" if exit_code != 0 else "No test output found between markers"
        return {
            "is_correct": False,
            "reasoning": f"{reason} (exit_code={exit_code}).\nLast 1000 chars:\n{output[-1000:]}",
            "metrics": {"fail_to_pass_rate": 0.0, "pass_to_pass_rate": 0.0},
        }

    # Parse test results
    parser = REPO_TO_PARSER.get(repo, parse_log_pytest)
    test_results = parser(test_output)

    # Grade
    status = grade(test_results, fail_to_pass, pass_to_pass)
    is_correct = status == "FULL"

    # Build reasoning
    f2p_results = [(t, test_results.get(t, "NOT_FOUND")) for t in fail_to_pass]
    p2p_results = [(t, test_results.get(t, "NOT_FOUND")) for t in pass_to_pass]

    lines = [f"Resolution: {status}"]
    lines.append(f"\nFAIL_TO_PASS ({len(fail_to_pass)}):")
    for t, s in f2p_results:
        lines.append(f"  {'✓' if s in (PASSED, XFAIL) else '✗'} {t}: {s}")
    if pass_to_pass:
        p2p_ok = sum(1 for _, s in p2p_results if s in (PASSED, XFAIL))
        lines.append(f"\nPASS_TO_PASS: {p2p_ok}/{len(pass_to_pass)} still passing")

    f2p_rate = sum(1 for _, s in f2p_results if s in (PASSED, XFAIL)) / max(len(fail_to_pass), 1)
    p2p_rate = sum(1 for _, s in p2p_results if s in (PASSED, XFAIL)) / max(len(pass_to_pass), 1)

    return {
        "is_correct": is_correct,
        "reasoning": "\n".join(lines),
        "metrics": {"resolution": status, "fail_to_pass_rate": f2p_rate, "pass_to_pass_rate": p2p_rate},
    }


def _extract_between_markers(text):
    start = text.find(START_TEST_OUTPUT)
    if start == -1:
        return ""
    start += len(START_TEST_OUTPUT)
    end = text.find(END_TEST_OUTPUT, start)
    return text[start:end] if end != -1 else text[start:]
