"""
Federal Register documents API adapter.

Why this source first (backlog task 005): ``config/feeds/core.json`` already
carries the Federal Register *public inspection* RSS feed and it produced zero
articles across the corpus. The API is the structured alternative -- documented,
stable, keyless, and a US Government work, so the licensing basis is the
cleanest of any source this project could add. See ``SOURCES.md``.

**Volume is the design problem.** Measured 2026-08-26 against the publication
week of Mon 2026-08-17 to Fri 2026-08-21, the API reports **469 documents** for
that week with no filter. Handing 469 unrelated rulemakings a day to clustering
would drown the brief. But over-filtering is the worse failure, because it is
silent -- so the filter is data, in ``config/sources/federal_register.json``,
one named query per intent, and every query is logged with its own hit count.
A query that stops matching is visible in the log rather than absorbed into a
total.

Filtering happens **server side only**. There is no client-side title denylist:
a denylist is exactly the mechanism that hides the document that mattered, and
it cannot be reviewed by reading the config.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .base import RawItem, SourceUnavailable, content_hash

logger = logging.getLogger(__name__)

DOCUMENTS_ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"

# Identify the client honestly, with a contact URL, per the licensing section of
# backlog task 005. The Federal Register API needs no key and sets no quota, so
# the only discipline available is our own.
USER_AGENT = "InsightWeaver/0.1 (+https://github.com/sam-aydlette/InsightWeaver)"

# Requested explicitly so that a field the API stops returning is visible as a
# 400 rather than as a quietly empty column.
REQUESTED_FIELDS: tuple[str, ...] = (
    "document_number",
    "title",
    "abstract",
    "html_url",
    "publication_date",
    "type",
    "agencies",
    "topics",
    "action",
    "docket_ids",
    "comments_close_on",
    "effective_on",
    "citation",
)

# httpx types its ``params`` list form with a permissive value type; naming it
# once keeps every builder below agreeing with the signature httpx expects.
QueryPairs = list[tuple[str, "str | int | float | bool | None"]]

DEFAULT_FILTER_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "sources" / "federal_register.json"
)


class FederalRegisterConfigError(ValueError):
    """Raised when the filter config is missing, malformed, or selects nothing."""


@dataclass(frozen=True)
class FederalRegisterQuery:
    """
    One named server-side query.

    ``agencies`` are Federal Register agency slugs (ORed together by the API);
    ``term`` is a full-text condition; ``types`` restricts document type
    (RULE / PRORULE / NOTICE / PRESDOCU). Conditions of different kinds are
    ANDed by the API, so ``agencies + term`` means "this agency AND this term",
    which is how a broad department is narrowed without a denylist.
    """

    name: str
    agencies: tuple[str, ...] = field(default_factory=tuple)
    term: str = ""
    types: tuple[str, ...] = field(default_factory=tuple)

    def conditions(self) -> QueryPairs:
        """Query-string pairs for this query's conditions, excluding the date."""
        pairs: QueryPairs = []
        for slug in self.agencies:
            pairs.append(("conditions[agencies][]", slug))
        for doc_type in self.types:
            pairs.append(("conditions[type][]", doc_type))
        if self.term:
            pairs.append(("conditions[term]", self.term))
        return pairs


@dataclass(frozen=True)
class FederalRegisterFilter:
    """The loaded contents of ``config/sources/federal_register.json``."""

    queries: tuple[FederalRegisterQuery, ...]
    per_page: int = 100
    max_pages: int = 5


def load_federal_register_filter(path: Path | str | None = None) -> FederalRegisterFilter:
    """
    Load and validate the filter config. Fails fast and loudly.

    A filter with no queries, or a query that constrains nothing, would fetch
    either everything or nothing -- both silently. Neither is loadable.
    """
    config_path = Path(path) if path is not None else DEFAULT_FILTER_PATH
    if not config_path.is_file():
        raise FederalRegisterConfigError(f"No Federal Register filter config at {config_path}")

    try:
        with open(config_path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise FederalRegisterConfigError(f"{config_path} is not valid JSON ({exc})")

    if not isinstance(raw, dict):
        raise FederalRegisterConfigError(f"{config_path}: top level must be a JSON object")

    raw_queries = raw.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise FederalRegisterConfigError(
            f"{config_path}: 'queries' must be a non-empty list. A filter that selects "
            f"nothing would produce an empty fetch with no error."
        )

    queries: list[FederalRegisterQuery] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_queries):
        where = f"{config_path}: queries[{index}]"
        if not isinstance(entry, dict):
            raise FederalRegisterConfigError(f"{where} must be an object")

        unknown = set(entry) - {"name", "agencies", "term", "types", "rationale"}
        if unknown:
            raise FederalRegisterConfigError(
                f"{where} has unknown key(s): {', '.join(sorted(unknown))}"
            )

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise FederalRegisterConfigError(f"{where}.name must be a non-empty string")
        if name in seen:
            raise FederalRegisterConfigError(f"{where}.name '{name}' is used twice")
        seen.add(name)

        agencies = _string_tuple(where, "agencies", entry.get("agencies", []))
        types = _string_tuple(where, "types", entry.get("types", []))
        term = entry.get("term", "")
        if not isinstance(term, str):
            raise FederalRegisterConfigError(f"{where}.term must be a string")

        if not agencies and not term:
            raise FederalRegisterConfigError(
                f"{where} constrains nothing: a query needs at least 'agencies' or 'term', "
                f"otherwise it selects the entire Federal Register."
            )

        queries.append(
            FederalRegisterQuery(name=name, agencies=agencies, term=term.strip(), types=types)
        )

    per_page = raw.get("per_page", 100)
    max_pages = raw.get("max_pages", 5)
    for label, value in (("per_page", per_page), ("max_pages", max_pages)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise FederalRegisterConfigError(f"{config_path}: '{label}' must be a positive integer")
    if per_page > 1000:
        raise FederalRegisterConfigError(f"{config_path}: 'per_page' must be 1000 or fewer")

    return FederalRegisterFilter(
        queries=tuple(queries), per_page=int(per_page), max_pages=int(max_pages)
    )


def _string_tuple(where: str, field_name: str, value: Any) -> tuple[str, ...]:
    """Validate one list-of-strings config field."""
    if not isinstance(value, list):
        raise FederalRegisterConfigError(f"{where}.{field_name} must be a list of strings")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise FederalRegisterConfigError(
                f"{where}.{field_name} must contain only non-empty strings, got {item!r}"
            )
    return tuple(item.strip() for item in value)


class FederalRegisterAdapter:
    """
    A :class:`~src.sources.base.SourceAdapter` over the documents API.

    One source row covers every query: the beat wants "the Federal Register",
    not "the Federal Register, cybersecurity query". Items are merged across
    queries and deduplicated by content hash before they are returned, which is
    also what makes the same document appearing under two agencies one article.
    """

    name = "Federal Register - Documents API"
    source_url = DOCUMENTS_ENDPOINT
    category = "federal_policy"

    def __init__(
        self,
        source_filter: FederalRegisterFilter | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: int = 30,
        requests_per_second: float = 1.0,
    ) -> None:
        self.filter = source_filter or load_federal_register_filter()
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout
        # Conservative by default: one request per second against a public
        # government API we are a guest on.
        self._min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._last_request = 0.0

    async def fetch(self, since: datetime) -> list[RawItem]:
        """
        Every document matching any configured query, published on or after
        ``since``'s calendar date.

        The API's date condition has day granularity, so ``since`` is truncated
        to its date. Re-fetching a day already ingested is free -- the content
        hash makes the re-insert a no-op -- which is why the window is allowed
        to be generous rather than exact.
        """
        client = self._client or httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        gte = since.date().isoformat()

        merged: dict[str, RawItem] = {}
        try:
            for query in self.filter.queries:
                documents = await self._run_query(client, query, gte)
                added = 0
                for document in documents:
                    item = self._to_raw_item(document)
                    if item is None:
                        continue
                    if item.guid not in merged:
                        merged[item.guid] = item
                        added += 1
                logger.info(
                    f"{self.name}: query '{query.name}' returned {len(documents)} document(s) "
                    f"since {gte}, {added} new after content-hash merge"
                )
        finally:
            if self._owns_client:
                await client.aclose()

        logger.info(f"{self.name}: {len(merged)} distinct document(s) since {gte}")
        return list(merged.values())

    async def _run_query(
        self, client: httpx.AsyncClient, query: FederalRegisterQuery, gte: str
    ) -> list[dict[str, Any]]:
        """Run one query, following pagination up to ``max_pages``."""
        params: QueryPairs = [
            ("per_page", str(self.filter.per_page)),
            ("order", "newest"),
            ("conditions[publication_date][gte]", gte),
        ]
        params.extend(query.conditions())
        params.extend(("fields[]", name) for name in REQUESTED_FIELDS)

        url: str | None = DOCUMENTS_ENDPOINT
        request_params: QueryPairs | None = params
        documents: list[dict[str, Any]] = []

        for page in range(1, self.filter.max_pages + 1):
            payload = await self._get_json(client, query, url, request_params)

            results = payload.get("results")
            count = payload.get("count")
            if results is None:
                # The API omits "results" entirely when count is 0. A missing
                # "results" with a non-zero count is a contract change, not a
                # quiet day, so it is an error.
                if count in (0, None) and not payload.get("total_pages"):
                    break
                raise SourceUnavailable(
                    self.name,
                    f"query '{query.name}' reported count={count} but returned no 'results' key "
                    f"-- the API contract may have changed",
                )
            if not isinstance(results, list):
                raise SourceUnavailable(
                    self.name, f"query '{query.name}' returned a non-list 'results'"
                )

            documents.extend(item for item in results if isinstance(item, dict))

            next_page = payload.get("next_page_url")
            if not next_page:
                break
            if page == self.filter.max_pages:
                # Truncation must be loud: a filter that has silently outgrown
                # its page budget is a filter that is silently losing documents.
                logger.warning(
                    f"{self.name}: query '{query.name}' hit the {self.filter.max_pages}-page "
                    f"ceiling with {payload.get('count')} matching document(s); results are "
                    f"TRUNCATED. Narrow the query or raise max_pages in "
                    f"config/sources/federal_register.json."
                )
                break
            url = str(next_page)
            request_params = None

        return documents

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        query: FederalRegisterQuery,
        url: str | None,
        params: QueryPairs | None,
    ) -> dict[str, Any]:
        """One rate-limited GET. Every failure mode becomes SourceUnavailable."""
        await self._throttle()
        try:
            response = await client.get(
                url or DOCUMENTS_ENDPOINT,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise SourceUnavailable(self.name, f"query '{query.name}': {exc}")

        if response.status_code != 200:
            raise SourceUnavailable(
                self.name,
                f"query '{query.name}': HTTP {response.status_code} from "
                f"{response.request.url} ({response.text[:200]})",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceUnavailable(
                self.name, f"query '{query.name}': response is not JSON ({exc})"
            )

        if not isinstance(payload, dict):
            raise SourceUnavailable(
                self.name, f"query '{query.name}': expected a JSON object, got {type(payload)}"
            )
        return payload

    async def _throttle(self) -> None:
        """Keep at least ``1 / requests_per_second`` between requests."""
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _to_raw_item(self, document: dict[str, Any]) -> RawItem | None:
        """
        Turn one API document into an article row.

        Returns ``None`` for a document with no title -- there is nothing to
        cluster or cite, and the RSS path applies the same guard.
        """
        title = (document.get("title") or "").strip()
        if not title:
            return None

        abstract = (document.get("abstract") or "").strip()
        doc_type = (document.get("type") or "").strip()
        agencies = [
            str(agency.get("name")).strip()
            for agency in document.get("agencies") or []
            if isinstance(agency, dict) and agency.get("name")
        ]
        topics = [str(topic).strip() for topic in document.get("topics") or [] if topic]
        agency_line = ", ".join(agencies)

        # Identity is content, not location: the same document is reachable at
        # its html_url, its citation URL and its public-inspection URL. Agencies
        # are part of the key because boilerplate titles ("Sunshine Act
        # Meetings", "Proposed Collection; Comment Request") recur verbatim
        # across unrelated agencies and are genuinely different documents.
        guid = content_hash(title, agency_line, doc_type, abstract)

        normalized_content = self._plain_text(document, title, doc_type, agency_line, topics)
        published = self._published_date(document.get("publication_date"))

        return RawItem(
            guid=guid,
            url=str(document.get("html_url") or ""),
            title=title,
            description=abstract,
            content=abstract,
            normalized_content=normalized_content,
            published_date=published,
            author=agency_line,
            categories=tuple(topics + ([doc_type] if doc_type else [])),
            language="en",
        )

    @staticmethod
    def _plain_text(
        document: dict[str, Any],
        title: str,
        doc_type: str,
        agency_line: str,
        topics: list[str],
    ) -> str:
        """
        The clean text the pipeline reasons over.

        Assembled from API fields only -- nothing is invented. The structured
        fields are included because for a Federal Register notice the deadline
        and the docket often carry more of the meaning than the abstract does,
        and many notices have no abstract at all.
        """
        parts = [title]
        if doc_type:
            parts.append(f"Document type: {doc_type}.")
        if agency_line:
            parts.append(f"Agencies: {agency_line}.")
        if topics:
            parts.append(f"Topics: {', '.join(topics)}.")

        action = (document.get("action") or "").strip()
        if action:
            parts.append(f"Action: {action}")

        dockets = [str(d).strip() for d in document.get("docket_ids") or [] if d]
        if dockets:
            parts.append(f"Docket: {', '.join(dockets)}.")

        for label, key in (
            ("Comments close on", "comments_close_on"),
            ("Effective", "effective_on"),
        ):
            value = document.get(key)
            if value:
                parts.append(f"{label}: {value}.")

        citation = (document.get("citation") or "").strip()
        number = (document.get("document_number") or "").strip()
        if citation or number:
            parts.append(f"Federal Register citation: {citation or number}.")

        abstract = (document.get("abstract") or "").strip()
        if abstract:
            parts.append(abstract)

        return " ".join(part for part in parts if part)

    @staticmethod
    def _published_date(value: Any) -> datetime | None:
        """
        ``publication_date`` is a naive calendar date; the schema stores naive
        datetimes (see ``src/utils.utcnow``), so midnight UTC is the honest
        rendering. A malformed date is dropped rather than guessed.
        """
        if not value:
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Unparseable Federal Register publication_date: {value!r}")
            return None
