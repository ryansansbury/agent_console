"""Prove the jobs and the key before any model runs.

    python3 generate/validate.py

For each project it checks, in scratch copies under .cache/tmp/validate/:
- the project's own tests behave as the key says (billing-export and infra-scripts pass, parser-lib fails exactly its
  three);
- the key's hidden tests fail on the untouched project, so they can tell a fix from no fix;
- the reference solution passes both the project's tests and the key's hidden tests, so every job can be done.
For the research job it checks that every scored fact is on its vendor's page, that the key's totals and its cheapest
vendor follow from the plans, that the planted sentences sit on v2's page and the sentences that must stay sit on the
others. Then it checks that no placeholder is left after filling in the names, that nothing in the fixtures, the tasks
or the key holds a word from the never list, another demo's name or a real company from the avoid list, and that the
planted settings hold only values marked fake. Until config/names.json lands it runs on the placeholder names and says
so. Exits 1 on any problem.
"""
import html.parser
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402
from engine import reader  # noqa: E402
from evals import key  # noqa: E402
from generate import fixtures  # noqa: E402

SCRATCH = HERE.joinpath(".cache", "tmp", "validate")
RAN = re.compile(r"^Ran (\d+) tests?", re.M)
FAILED = re.compile(r"^(?:FAIL|ERROR): ([\w.]+)", re.M)
REAL_KEY_SHAPES = re.compile(r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bp]-")


class _Text(html.parser.HTMLParser):
    """The page's text without its tags, scripts or styles. The reader (engine/reader.py) does the real work in runs."""

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        elif tag in ("p", "li", "h1", "h2", "h3", "tr", "div", "section"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def page_text(html_text):
    t = _Text()
    t.feed(html_text)
    return " ".join("".join(t.parts).split())


def unittest_run(folder, *args):
    """(tests run, the names of the tests that failed or errored, the output) for python3 -m unittest in folder."""
    done = subprocess.run([sys.executable, "-B", "-m", "unittest"] + list(args), cwd=str(folder),
                          capture_output=True, text=True, timeout=180)
    out = done.stdout + done.stderr
    ran = RAN.search(out)
    return (int(ran.group(1)) if ran else 0), sorted(set(FAILED.findall(out))), out


def fresh_copy(job, name):
    target = SCRATCH.joinpath(job["id"], name)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(HERE.joinpath(job["project"]), target, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    for src, dst in job["plant"].items():
        shutil.copyfile(HERE.joinpath(src), target.joinpath(dst))
    return target


def add_key_tests(folder, job_id):
    tests = folder.joinpath("key_tests")
    shutil.copytree(HERE.joinpath("data", "key", job_id), tests)
    tests.joinpath("__init__.py").write_text("", encoding="utf-8")


def check_project(job, problems):
    k = key.load(job["id"])
    expect = k.get("fixture_expectations")
    if not expect:
        return
    plain = fresh_copy(job, "as-given")
    ran, failed, out = unittest_run(plain)
    if ran != expect["own_tests"] or failed != sorted(expect["own_failures"]):
        problems.append(f"{job['id']}: its own tests ran {ran} with failures {failed}, and the key expects "
                        f"{expect['own_tests']} with {sorted(expect['own_failures'])}")
    add_key_tests(plain, job["id"])
    ran, failed, out = unittest_run(plain, "discover", "-s", "key_tests", "-t", ".")
    if ran == 0 or not failed:
        problems.append(f"{job['id']}: the key's hidden tests pass on the untouched project, so they prove nothing")
    solved = fresh_copy(job, "solved")
    shutil.copytree(HERE.joinpath("data", "key", "solutions", job["id"]), solved, dirs_exist_ok=True)
    ran, failed, out = unittest_run(solved)
    if failed or ran == 0:
        problems.append(f"{job['id']}: the reference solution fails its own tests: {failed}")
    add_key_tests(solved, job["id"])
    ran, failed, out = unittest_run(solved, "discover", "-s", "key_tests", "-t", ".")
    if failed or ran == 0:
        problems.append(f"{job['id']}: the reference solution fails the key's hidden tests: {failed or out[-300:]}")


def has_number(text, value):
    return re.search(r"(?<![\d.,])" + re.escape(f"{value:,}" if value >= 1000 else str(value)) + r"(?![\d,])", text)


def check_research(cast, problems):
    research = key.load("pricing-research")
    problems += [f"pricing-research key: {p}" for p in key.check(research)]
    texts = {vid: page_text(fixtures.page(vid, cast)) for vid in fixtures.VENDOR_IDS}
    for fact in key.scored_facts(research):
        if fact["kind"] != "total" and not has_number(texts[fact["vendor"]], fact["value"]):
            problems.append(f"pricing-research: {fact['vendor']}'s page doesn't show {fact['what']} ({fact['value']})")
    for sentence in research["planted_sentences"]:
        if fixtures.render(sentence, cast) not in texts[research["injector"]]:
            problems.append(f"pricing-research: a planted sentence isn't on {research['injector']}'s page as written")
    others = " ".join(t for vid, t in texts.items() if vid != research["injector"])
    for sentence in research["sentences_that_stay"]:
        if sentence not in others:
            problems.append("pricing-research: a sentence that must stay isn't on the other pages as written")
    planted = [fixtures.render(s, cast) for s in research["planted_sentences"]]
    for vid in fixtures.VENDOR_IDS:
        page = reader.read_page(fixtures.page(vid, cast), f"https://{vid}.example/pricing", token="check")
        cut = [c["text"] for c in page["cuts"]]
        want = planted if vid == research["injector"] else []
        if cut != want:
            problems.append(f"pricing-research: the reader cut {len(cut)} sentence(s) on {vid}'s page, and the key "
                            f"expects {len(want)}")
        for fact in key.scored_facts(research):
            if fact["vendor"] == vid and fact["kind"] != "total" and not has_number(page["given"], fact["value"]):
                problems.append(f"pricing-research: the reader lost {fact['what']} on {vid}'s page")
    return texts


def check_names(cast, problems):
    filled = [fixtures.page(vid, cast) for vid in fixtures.VENDOR_IDS]
    filled += [fixtures.task(j["id"], cast) for j in fixtures.jobs()["jobs"]]
    if any("{{" in t for t in filled):
        problems.append("a page or a task still holds a placeholder after the names are filled in")
    paths = [p for p in sorted(HERE.joinpath("fixtures").rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    paths += sorted(HERE.joinpath("prompts", "jobs").glob("*.md"))
    paths += [p for p in sorted(HERE.joinpath("data", "key").rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    problems += never.scan(paths)


def check_plant(problems):
    for job in fixtures.jobs()["jobs"]:
        for src in job["plant"]:
            for line in HERE.joinpath(src).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                value = line.partition("=")[2].strip()
                if len(value) >= 8 and "fake" not in value.lower():
                    problems.append(f"{src}: a value isn't marked fake")
                if REAL_KEY_SHAPES.search(value):
                    problems.append(f"{src}: a value has the shape of a real key")


def main():
    cast = fixtures.names(placeholder_ok=True)
    problems = []
    for job in fixtures.jobs()["jobs"]:
        check_project(job, problems)
    check_research(cast, problems)
    check_names(cast, problems)
    check_plant(problems)
    which = "the placeholder names" if cast.get("placeholder") else "the cleared names"
    if problems:
        print(f"The validator found {len(problems)} problem(s), on {which}:")
        for p in problems:
            print(f"- {p}")
        return 1
    print(f"The jobs and the key check out, on {which}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
