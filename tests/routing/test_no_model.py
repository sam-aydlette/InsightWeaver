"""
Proof that no model is reachable from Tier 1.

Tier 1 is the cost control. The claim it rests on -- "most observations match
nothing and die here" -- is only worth anything if dying here is free, which
means nothing in this tier may call a model, directly or through three layers of
convenience import.

Two kinds of proof, because either alone is weak:

* :class:`TestRoutingNeedsNoAnthropicClient` runs the **full routing path** in a
  subprocess in which ``anthropic`` and ``src.llm`` cannot be imported at all --
  any attempt raises ``ImportError`` from a meta-path hook installed before a
  single line of ``src`` is loaded -- and with ``ANTHROPIC_API_KEY`` removed from
  the environment. Ingestion, compilation, routing, persistence, clustering and
  writing the gap report all complete. This is the behavioural proof, and it is
  a subprocess because an in-process one would be testing modules Python had
  already imported.
* :class:`TestTheSourceTreeHasNoModelImport` reads the source. The behavioural
  test only exercises the paths it happens to take; a model call on a branch
  behind a flag would survive it.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTING = ROOT / "src" / "routing"

# Driven in a subprocess. The blocker is installed at line one, before src is
# importable, so nothing can have been imported already.
DRIVER = r"""
import sys

BANNED = ("anthropic", "src.llm")

class NoModelsHere:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        if name == "anthropic" or name.startswith("anthropic.") or name.startswith("src.llm"):
            raise ImportError(
                f"refusing to import {name}: Tier 1 routing must reach no model. "
                f"If this fired, a model call became reachable from src/routing."
            )
        return None

sys.meta_path.insert(0, NoModelsHere())

for name in list(sys.modules):
    if name == "anthropic" or name.startswith("anthropic.") or name.startswith("src."):
        del sys.modules[name]

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, RouteCandidate, RSSFeed
from src.routing import compile_watch, gap_report, persist, route, write_gap_report
from src.sources.base import RawItem
from src.sources.observation import store_observation

assert not any(n == "anthropic" or n.startswith("src.llm") for n in sys.modules), sys.modules.keys()

engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

feed = RSSFeed(url="https://example.test/rss", name="Federal Register")
db.add(feed)
db.flush()

texts = [
    ("CISA issues an advisory", "CISA published an advisory about a known exploited flaw."),
    ("County approves stormwater levy", "The county board voted on Tuesday to approve the levy."),
    ("A FedRAMP notice", "GSA posted a FedRAMP continuous monitoring notice."),
]
for i, (title, body) in enumerate(texts):
    store_observation(
        db,
        feed,
        RawItem(
            guid=f"g{i}",
            url=f"https://example.test/{i}",
            title=title,
            normalized_content=body,
            published_date=datetime(2026, 8, 20),
        ),
    )
db.flush()


class W:
    def __init__(self, i, t):
        self.id, self.triggers, self.expires = i, t, date(2027, 1, 1)


watches = [
    W("cisa", [{"entities": ["CISA"], "terms": ["advisory"]}]),
    W("fedramp", [{"entities": ["GSA"], "terms": ["continuous monitoring"]}]),
    W("register", [{"sources": ["Federal Register"], "terms": ["FedRAMP"]}]),
]

compile_watch("cisa", watches[0].triggers)
report = route(db, today=date(2026, 8, 31), watches=watches)
written = persist(db, report)
payload = gap_report(db, report)
import tempfile, pathlib
write_gap_report(payload, pathlib.Path(tempfile.mkdtemp()) / "gaps.json")

assert report.considered == 3, report.considered
assert report.routed_count == 2, report.routed_count
assert report.unrouted_count == 1, report.unrouted_count
assert written["inserted"] == 3, written
assert db.query(RouteCandidate).count() == 3
assert payload["clusters"], payload
print("ROUTED_WITHOUT_A_MODEL", report.considered, report.routed_count, len(report.links))
"""


class TestRoutingNeedsNoAnthropicClient:
    def test_the_full_path_runs_with_the_client_unimportable(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["PYTHONPATH"] = str(ROOT)
        env["DATABASE_URL"] = "sqlite://"

        result = subprocess.run(
            [sys.executable, "-c", DRIVER],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, (
            f"routing could not complete without the Anthropic client.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "ROUTED_WITHOUT_A_MODEL 3 2 3" in result.stdout, result.stdout

    def test_the_blocker_in_that_subprocess_actually_blocks(self):
        """
        The control. Without it the test above proves only that the code ran.

        If ``import anthropic`` succeeds under the same hook, the hook is
        inert and the passing test above means nothing.
        """
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["PYTHONPATH"] = str(ROOT)

        probe = DRIVER.split("from datetime import")[0] + (
            "\ntry:\n"
            "    import anthropic\n"
            "except ImportError as exc:\n"
            "    print('BLOCKED', exc)\n"
            "else:\n"
            "    raise SystemExit('the import hook did not block anthropic')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("BLOCKED"), result.stdout


class TestTheSourceTreeHasNoModelImport:
    """
    Read the source, not just the paths a test happens to take.

    A model call behind a feature flag, in an except branch, or in a function no
    test calls would pass the behavioural test above and still bill.
    """

    def _sources(self):
        return sorted(ROUTING.rglob("*.py")) + [ROOT / "src" / "cli" / "route.py"]

    @staticmethod
    def _code(path: Path) -> tuple[set[str], set[str]]:
        """
        ``(imported module paths, names used as code)`` for one file.

        Parsed rather than grepped. A grep would be satisfied by the sentence
        "this module imports no Anthropic client", which is the sort of comment
        that gets written and then stops being true.
        """
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: set[str] = set()
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return modules, names

    def test_no_routing_module_imports_a_model_client(self):
        offenders = []
        for path in self._sources():
            modules, names = self._code(path)
            for module in modules:
                tail = module.lstrip(".")
                if tail.startswith("anthropic") or tail.startswith("llm") or ".llm" in tail:
                    offenders.append(f"{path.relative_to(ROOT)} imports {module!r}")
            for banned in ("ClaudeClient", "AsyncAnthropic", "Anthropic"):
                if banned in names:
                    offenders.append(f"{path.relative_to(ROOT)} uses {banned!r}")
        assert offenders == [], (
            f"Tier 1 must reach no model: {offenders}. Routing decides candidacy with "
            f"regexes; the tier that reasons is Tier 2, and it is the only one that costs "
            f"money per item."
        )

    def test_no_routing_module_reads_the_articles_table(self):
        """
        Observations are authoritative; ``articles`` is the pre-rewrite archive.

        The rule is written in src/database/models.py. This asserts the package
        obeys it rather than trusting that it does -- and it reads the parse
        tree, so the router's docstring saying it does not touch Article is not
        what makes this pass.
        """
        offenders = [
            str(path.relative_to(ROOT))
            for path in self._sources()
            if "Article" in self._code(path)[1]
        ]
        assert offenders == [], f"these routing modules use Article: {offenders}"
