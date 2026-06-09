from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from inference import InferenceConfig
from inference.providers import (
    BrowserAutomationUnavailableError,
    ProviderError,
    ProviderFactory,
    ProviderLoginRequiredError,
    ProviderNotConfiguredError,
    ProviderHit,
    order_providers,
)

from .config import SECTION_QUERY_TEMPLATES
from .models import Chapter1Source


class Chapter1RetrievalService:
    def __init__(self, config: InferenceConfig | None = None) -> None:
        self.config = config or InferenceConfig()
        self.records: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.last_record: dict[str, Any] = {}

    def retrieve_for_section(
        self,
        *,
        product_name: str,
        section_key: str,
        section_title: str,
        max_results: int = 5,
    ) -> list[Chapter1Source]:
        queries = self._build_queries(product_name=product_name, section_key=section_key)
        record: dict[str, Any] = {
            "section_key": section_key,
            "section_title": section_title,
            "queries": list(queries),
            "sources": [],
            "warnings": [],
        }
        self.last_record = record
        self.records.append(record)

        if not queries:
            warning = f"{section_title} 未配置检索关键词"
            self._append_warning(record, warning)
            return []

        providers = []
        try:
            providers = order_providers(self.config.providers, self.config.provider_priority)
        except Exception as exc:  # pragma: no cover - defensive
            self._append_warning(record, f"检索配置不可用：{exc}")
            return []

        if not providers:
            warning = f"{section_title} 没有可用的检索 provider"
            self._append_warning(record, warning)
            return []

        sources: list[Chapter1Source] = []
        seen_urls: set[str] = set()
        source_index = 0
        for query in queries:
            provider_errors: list[str] = []
            query_hits: list[ProviderHit] = []
            for provider in providers:
                try:
                    hits = provider.search(query, max_results=max_results, market_path=[section_key])
                except (BrowserAutomationUnavailableError, ProviderLoginRequiredError, ProviderNotConfiguredError, ProviderError) as exc:
                    provider_errors.append(f"{provider.name}:{exc}")
                    continue
                except Exception as exc:  # pragma: no cover - defensive
                    provider_errors.append(f"{provider.name}:{exc}")
                    continue
                if hits:
                    query_hits.extend(hits[:max_results])
                if len(query_hits) >= max_results:
                    break

            if provider_errors:
                record.setdefault("provider_errors", []).extend(provider_errors)

            for hit in query_hits:
                url = str(hit.url or "").strip()
                if url and url in seen_urls:
                    continue
                source_index += 1
                source = self._hit_to_source(hit, section_key=section_key, source_index=source_index)
                sources.append(source)
                if url:
                    seen_urls.add(url)
                if len(sources) >= max_results:
                    break
            if len(sources) >= max_results:
                break

        if not sources:
            warning = f"{section_title} 未检索到可用资料"
            self._append_warning(record, warning)
        record["sources"] = [source.model_dump(mode="python") for source in sources]
        return sources

    def _build_queries(self, *, product_name: str, section_key: str) -> list[str]:
        templates = SECTION_QUERY_TEMPLATES.get(section_key, [])
        return [template.format(product_name=product_name).strip() for template in templates if template.format(product_name=product_name).strip()]

    def _hit_to_source(self, hit: ProviderHit, *, section_key: str, source_index: int) -> Chapter1Source:
        extracted_facts = []
        if str(hit.snippet or "").strip():
            extracted_facts.append(str(hit.snippet).strip())
        if str(hit.quote_text or "").strip() and str(hit.quote_text).strip() not in extracted_facts:
            extracted_facts.append(str(hit.quote_text).strip())
        return Chapter1Source(
            source_id=f"{section_key}_{source_index:03d}",
            title=str(hit.title or "").strip(),
            url=str(hit.url or "").strip(),
            publisher=str(hit.provider or "").strip(),
            publish_date="",
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            source_type="web",
            reliability_level="verified" if bool(hit.source_verified) else "medium",
            related_sections=[section_key],
            extracted_facts=extracted_facts,
            raw_excerpt=str(hit.snippet or "").strip(),
        )

    def _append_warning(self, record: dict[str, Any], warning: str) -> None:
        text = str(warning or "").strip()
        if not text:
            return
        self.warnings.append(text)
        record.setdefault("warnings", []).append(text)

