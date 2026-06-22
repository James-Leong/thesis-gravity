from __future__ import annotations

import hashlib
import json
import logging
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

import fitz
from agno.media import Image

from app.agents.checklist_reviewer import get_checklist_reviewer_agent
from app.agents.global_synopsis_reviewer import get_global_synopsis_reviewer_agent
from app.agents.local_segment_reviewer import get_local_segment_reviewer_agent
from app.agents.vision_checklist_reviewer import get_vision_checklist_reviewer_agent
from app.core.config import settings
from app.core.constants import (
    ANALYSIS_STATUS_COMPLETED,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_RUNNING,
    THESIS_STATUS_ANALYSIS_DONE,
)
from app.db import SessionLocal
from app.models import AnalysisLLMCallLog, AnalysisTask, Notification
from app.schemas.analysis import (
    AnalysisCheck,
    AnalysisLLMUsagePhaseSummary,
    AnalysisLLMUsageSummary,
    GlobalSynopsisReview,
    AnalysisIssue,
    AnalysisLayerSummary,
    AnalysisResult,
    ChecklistBatchResult,
    LocalSegmentReview,
)
from app.services.analysis_checklist import ChecklistDefinition, extract_query_terms, parse_reference_checklist
from app.services.figure_table_assets import FigureTableAsset, extract_figure_table_assets
from app.services.analysis_page_mapping import map_document_page_labels
from app.services.analysis_rules import ExtractedPage, VisualPageIndex, build_visual_page_index, evaluate_rule_check
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)
llm_metrics_logger = logging.getLogger("app.llm_metrics")


@dataclass(frozen=True)
class SegmentReviewEnvelope:
    page_start: int
    page_end: int
    review: LocalSegmentReview


@dataclass(frozen=True)
class DefinitionBatch:
    label: str
    page_numbers: list[int]
    definitions: list[ChecklistDefinition]
    asset_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VisionBatchImages:
    images: list[Image]
    image_context: list[str]
    source: str


@dataclass
class LLMCallTrace:
    phase: str
    request_group: str | None
    prompt_hash: str
    prompt_prefix_hash: str
    prompt_prefix_chars: int
    input_chars: int
    output_chars: int
    status: str
    model_id: str | None = None
    model_provider: str | None = None
    duration_ms: int = 0
    time_to_first_token_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float | None = None
    check_ids: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    metrics: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class AnalysisRuntimeContext:
    analysis_task_id: int | None = None
    llm_calls: list[LLMCallTrace] = field(default_factory=list)


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return settings.base_dir / path


def _load_reference_text() -> str:
    path = settings.reference_doc_path
    if not path.exists():
        return ""
    if path.suffix.lower() not in {".md", ".txt"}:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_pdf_pages(pdf_path: Path) -> list[ExtractedPage]:
    doc = fitz.open(str(pdf_path))
    total_pdf_pages = len(doc)
    if total_pdf_pages > settings.max_pages:
        doc.close()
        raise ValueError(f"PDF 页数为 {total_pdf_pages} 页，超过当前分析上限 {settings.max_pages} 页。")

    total_pages = total_pdf_pages
    pages: list[ExtractedPage] = []

    for index in range(total_pages):
        page = doc.load_page(index)
        text = page.get_text().strip()
        if not text:
            text = "(no extractable text)"
        pages.append(ExtractedPage(number=index + 1, text=text))

    doc.close()
    page_labels = map_document_page_labels(pages)
    return [
        ExtractedPage(
            number=page.number,
            text=page.text,
            document_page_label=page_labels.get(page.number).label if page.number in page_labels else None,
            document_page_number=(
                page_labels[page.number].sequence_value
                if page.number in page_labels and page_labels[page.number].kind == "arabic"
                else None
            ),
            document_page_kind=page_labels.get(page.number).kind if page.number in page_labels else None,
        )
        for page in pages
    ]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize_response_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if hasattr(content, "model_dump_json"):
        return content.model_dump_json(exclude_none=True)
    return json.dumps(content, ensure_ascii=False, default=str)


def _coerce_metrics_dict(metrics: Any) -> dict[str, Any] | None:
    if metrics is None:
        return None
    if hasattr(metrics, "to_dict"):
        return metrics.to_dict()
    if isinstance(metrics, dict):
        return metrics
    if hasattr(metrics, "__dict__"):
        return asdict(metrics)
    return None


def _extract_model_identity(response: Any, metrics_dict: dict[str, Any] | None) -> tuple[str | None, str | None]:
    model_id = getattr(response, "model", None)
    model_provider = getattr(response, "model_provider", None)
    if model_id and model_provider:
        return model_id, model_provider

    details = metrics_dict.get("details") if metrics_dict else None
    if isinstance(details, dict):
        for model_entries in details.values():
            if not model_entries:
                continue
            first = model_entries[0]
            if isinstance(first, dict):
                return model_id or first.get("id"), model_provider or first.get("provider")
    return model_id, model_provider


def _record_llm_call(
    runtime_context: AnalysisRuntimeContext | None,
    trace: LLMCallTrace,
) -> None:
    if runtime_context is not None:
        runtime_context.llm_calls.append(trace)

    cache_hit_rate = None
    if trace.input_tokens > 0:
        cache_hit_rate = round(trace.cache_read_tokens / trace.input_tokens, 4)

    llm_metrics_logger.info(
        "phase=%s status=%s group=%s model=%s provider=%s chars=%s/%s tokens=%s/%s/%s cache=%s/%s cache_hit=%s duration_ms=%s pages=%s checks=%s prompt_hash=%s prefix_hash=%s",
        trace.phase,
        trace.status,
        trace.request_group,
        trace.model_id,
        trace.model_provider,
        trace.input_chars,
        trace.output_chars,
        trace.input_tokens,
        trace.output_tokens,
        trace.total_tokens,
        trace.cache_read_tokens,
        trace.cache_write_tokens,
        cache_hit_rate,
        trace.duration_ms,
        trace.page_numbers,
        len(trace.check_ids),
        trace.prompt_hash[:12],
        trace.prompt_prefix_hash[:12],
    )


def _run_agent_with_tracking(
    *,
    phase: str,
    prompt: str,
    runtime_context: AnalysisRuntimeContext | None,
    request_group: str | None = None,
    check_ids: list[str] | None = None,
    page_numbers: list[int] | None = None,
    images: list[Image] | None = None,
    metadata: dict[str, Any] | None = None,
    agent_getter: Any,
) -> Any:
    started = perf_counter()
    prefix_chars = min(len(prompt), 4096)
    prompt_hash = _hash_text(prompt)
    prompt_prefix_hash = _hash_text(prompt[:prefix_chars])

    try:
        response = agent_getter().run(prompt, images=images) if images is not None else agent_getter().run(prompt)
    except Exception as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        _record_llm_call(
            runtime_context,
            LLMCallTrace(
                phase=phase,
                request_group=request_group,
                prompt_hash=prompt_hash,
                prompt_prefix_hash=prompt_prefix_hash,
                prompt_prefix_chars=prefix_chars,
                input_chars=len(prompt),
                output_chars=0,
                status="failed",
                duration_ms=duration_ms,
                check_ids=list(check_ids or []),
                page_numbers=list(page_numbers or []),
                metadata=metadata,
                error_message=str(exc),
            ),
        )
        raise

    duration_ms = int((perf_counter() - started) * 1000)
    metrics_dict = _coerce_metrics_dict(getattr(response, "metrics", None))
    model_id, model_provider = _extract_model_identity(response, metrics_dict)
    output_text = _serialize_response_content(getattr(response, "content", None))

    _record_llm_call(
        runtime_context,
        LLMCallTrace(
            phase=phase,
            request_group=request_group,
            prompt_hash=prompt_hash,
            prompt_prefix_hash=prompt_prefix_hash,
            prompt_prefix_chars=prefix_chars,
            input_chars=len(prompt),
            output_chars=len(output_text),
            status="completed",
            model_id=model_id,
            model_provider=model_provider,
            duration_ms=duration_ms,
            time_to_first_token_ms=int((metrics_dict or {}).get("time_to_first_token", 0) * 1000),
            input_tokens=int((metrics_dict or {}).get("input_tokens", 0)),
            output_tokens=int((metrics_dict or {}).get("output_tokens", 0)),
            total_tokens=int((metrics_dict or {}).get("total_tokens", 0)),
            cache_read_tokens=int((metrics_dict or {}).get("cache_read_tokens", 0)),
            cache_write_tokens=int((metrics_dict or {}).get("cache_write_tokens", 0)),
            reasoning_tokens=int((metrics_dict or {}).get("reasoning_tokens", 0)),
            cost=(metrics_dict or {}).get("cost"),
            check_ids=list(check_ids or []),
            page_numbers=list(page_numbers or []),
            metrics=metrics_dict,
            metadata=metadata,
        ),
    )
    return response


def analyze_pdf(file_path: str, runtime_context: AnalysisRuntimeContext | None = None) -> AnalysisResult:
    pdf_path = _resolve_path(file_path)
    pages = _extract_pdf_pages(pdf_path)
    if not pages:
        raise ValueError("No extractable pages found in the PDF.")
    visual_page_index = build_visual_page_index(pages, pdf_path)
    local_segment_reviews = _run_local_segment_reviews(pages, runtime_context)

    reference_text = _load_reference_text()
    parsed_reference = parse_reference_checklist(reference_text)

    rule_definitions = [item for item in parsed_reference.checklist if item.layer == "rule"]
    text_definitions = [item for item in parsed_reference.checklist if item.layer == "text_model"]
    vision_definitions = [item for item in parsed_reference.checklist if item.layer == "vision_model"]

    checks_by_id: dict[str, AnalysisCheck] = {}

    for definition in rule_definitions:
        checks_by_id[definition.check_id] = evaluate_rule_check(definition, pages, total_pages=len(pages))

    for check in _run_text_model_checks(text_definitions, pages, runtime_context):
        checks_by_id[check.check_id] = check

    for check in _run_vision_model_checks(vision_definitions, pages, pdf_path, visual_page_index, runtime_context):
        checks_by_id[check.check_id] = check

    ordered_checks = [
        checks_by_id[item.check_id] for item in parsed_reference.checklist if item.check_id in checks_by_id
    ]
    ordered_checks = _apply_page_mapping_to_checks(ordered_checks, pages)
    layer_summaries = _build_layer_summaries(ordered_checks)
    issues = _build_issues(ordered_checks)

    primary_checks = [check for check in ordered_checks if check.layer != "vision_model"]
    failed_count = sum(check.status == "failed" for check in primary_checks)
    manual_count = sum(check.status == "needs_manual_review" for check in primary_checks)
    ready_for_mentor = not any(
        check.status == "failed" and check.severity in {"medium", "high"} for check in primary_checks
    )
    summary = _build_summary(ordered_checks, layer_summaries)
    global_summary = _build_global_summary(pages, local_segment_reviews, ordered_checks, runtime_context)
    llm_usage_summary = _build_llm_usage_summary(runtime_context.llm_calls if runtime_context else [])
    visual_summary = _build_visual_summary(ordered_checks)
    overall_assessment = _build_overall_assessment(failed_count, manual_count)

    return AnalysisResult(
        summary=summary,
        global_summary=global_summary,
        visual_summary=visual_summary,
        issues=issues,
        checks=ordered_checks,
        layer_summaries=layer_summaries,
        llm_usage_summary=llm_usage_summary,
        overall_assessment=overall_assessment,
        ready_for_mentor=ready_for_mentor,
    )


def _run_text_model_checks(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
    runtime_context: AnalysisRuntimeContext | None,
) -> list[AnalysisCheck]:
    if not definitions:
        return []

    all_assessments: dict[str, Any] = {}

    for batch in _build_text_segment_batches(definitions, pages):
        prompt = _build_text_batch_prompt(batch, pages)
        parsed: ChecklistBatchResult | None = None
        for attempt in range(3):
            try:
                response = _run_agent_with_tracking(
                    phase="text_checklist",
                    prompt=prompt,
                    runtime_context=runtime_context,
                    request_group=batch.label,
                    check_ids=[item.check_id for item in batch.definitions],
                    page_numbers=batch.page_numbers,
                    metadata={"definition_count": len(batch.definitions)},
                    agent_getter=get_checklist_reviewer_agent,
                )
                parsed = _parse_checklist_batch_result(response.content)
                break
            except Exception as exc:
                logger.warning(
                    "text_checklist batch %s 解析失败 (attempt %d/3): %s",
                    batch.label,
                    attempt + 1,
                    exc,
                )
        if parsed is None:
            logger.error("text_checklist batch %s 连续 3 次解析失败，跳过该批检查项", batch.label)
            continue
        segment_assessments = {item.check_id: item for item in parsed.assessments}
        _deduplicate_assessments(all_assessments, segment_assessments)

    results: list[AnalysisCheck] = []
    for definition in definitions:
        assessment = all_assessments.get(definition.check_id)
        if assessment is None:
            results.append(
                _fallback_check(
                    definition,
                    status="needs_manual_review",
                    rationale="模型没有返回这一项的评估结果。",
                    suggestion="请人工复核这一项，或重新触发分析。",
                )
            )
            continue
        results.append(
            AnalysisCheck(
                check_id=definition.check_id,
                title=definition.title,
                source_section=definition.source_section,
                requirement=definition.requirement,
                layer=definition.layer,
                severity=definition.severity,
                status=assessment.status,
                rationale=assessment.rationale,
                suggestion=assessment.suggestion,
                pages=sorted(set(page for page in assessment.pages if page >= 1)),
            )
        )
    return results


def _run_vision_model_checks(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
    pdf_path: Path,
    visual_page_index: VisualPageIndex,
    runtime_context: AnalysisRuntimeContext | None,
) -> list[AnalysisCheck]:
    if not definitions:
        return []

    if not settings.vision_llm_model_id or not settings.vision_llm_api_key:
        return [
            _fallback_check(
                definition,
                status="needs_manual_review",
                rationale="当前未配置多模态模型，视觉类检查项已保留为人工复核。",
                suggestion="如需自动检查图表清晰度、坐标轴和版式，请配置 `VISION_LLM_*` 环境变量。",
            )
            for definition in definitions
        ]

    all_assessments: dict[str, Any] = {}
    fallback_pages_by_check: dict[str, list[int]] = defaultdict(list)
    with tempfile.TemporaryDirectory(prefix="thesis-vision-") as temp_dir:
        temp_path = Path(temp_dir)
        figure_table_assets = _extract_vision_figure_table_assets(definitions, pdf_path, temp_path)
        for batch in _build_vision_definition_batches(definitions, pages, visual_page_index, figure_table_assets):
            for definition in batch.definitions:
                fallback_pages_by_check[definition.check_id].extend(batch.page_numbers)
            rendered = _render_vision_batch_images(pdf_path, batch, pages, temp_path, figure_table_assets)
            prompt = _build_vision_batch_prompt(batch, pages, rendered)
            parsed: ChecklistBatchResult | None = None
            for attempt in range(3):
                try:
                    response = _run_agent_with_tracking(
                        phase="vision_checklist",
                        prompt=prompt,
                        runtime_context=runtime_context,
                        request_group=batch.label,
                        check_ids=[item.check_id for item in batch.definitions],
                        page_numbers=batch.page_numbers,
                        images=rendered.images,
                        metadata={
                            "definition_count": len(batch.definitions),
                            "image_count": len(rendered.images),
                            "image_source": rendered.source,
                        },
                        agent_getter=get_vision_checklist_reviewer_agent,
                    )
                    parsed = _parse_checklist_batch_result(response.content)
                    break
                except Exception as exc:
                    logger.warning(
                        "vision_checklist batch %s 解析失败 (attempt %d/3): %s",
                        batch.label,
                        attempt + 1,
                        exc,
                    )
            if parsed is None:
                logger.error("vision_checklist batch %s 连续 3 次解析失败，跳过该批检查项", batch.label)
                # fall through so definitions get fallback status
                parsed = ChecklistBatchResult()
            assessments = {item.check_id: item for item in parsed.assessments}
            _deduplicate_assessments(all_assessments, assessments)

    results: list[AnalysisCheck] = []
    for definition in definitions:
        assessment = all_assessments.get(definition.check_id)
        if assessment is None:
            fallback_pages = sorted(set(page for page in fallback_pages_by_check[definition.check_id] if page >= 1))
            results.append(
                AnalysisCheck(
                    check_id=definition.check_id,
                    title=definition.title,
                    source_section=definition.source_section,
                    requirement=definition.requirement,
                    layer=definition.layer,
                    severity=definition.severity,
                    status="needs_manual_review",
                    rationale="视觉模型没有返回这一项的评估结果，已保留候选页面供人工复核。",
                    suggestion="请人工复核对应页面的图表和版式，或重新触发视觉分析。",
                    pages=fallback_pages,
                )
            )
            continue
        results.append(
            AnalysisCheck(
                check_id=definition.check_id,
                title=definition.title,
                source_section=definition.source_section,
                requirement=definition.requirement,
                layer=definition.layer,
                severity=definition.severity,
                status=assessment.status,
                rationale=assessment.rationale,
                suggestion=assessment.suggestion,
                pages=sorted(set(page for page in assessment.pages if page >= 1)),
            )
        )

    return results


def _build_text_segment_batches(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
) -> list[DefinitionBatch]:
    batch_size = max(1, settings.local_review_page_batch_size)
    grouped: dict[str, list[ChecklistDefinition]] = defaultdict(list)
    for definition in definitions:
        grouped[_definition_group_label(definition)].append(definition)

    batches: list[DefinitionBatch] = []
    for segment_pages in _chunk_pages(pages, batch_size):
        page_numbers = [page.number for page in segment_pages]
        segment_label = f"PDF pages {segment_pages[0].number}-{segment_pages[-1].number}"
        for group_label, group_definitions in grouped.items():
            for definition_batch in _chunked(group_definitions, settings.max_check_items_per_batch):
                batches.append(
                    DefinitionBatch(
                        label=f"{segment_label} / {group_label}",
                        page_numbers=page_numbers,
                        definitions=definition_batch,
                    )
                )
    return batches


def _deduplicate_assessments(
    merged: dict[str, Any],
    new_assessments: dict[str, Any],
) -> None:
    status_order = ["passed", "needs_manual_review", "failed"]
    for check_id, assessment in new_assessments.items():
        if check_id not in merged:
            merged[check_id] = assessment
            continue
        existing = merged[check_id]
        existing_rank = status_order.index(existing.status) if existing.status in status_order else 0
        new_rank = status_order.index(assessment.status) if assessment.status in status_order else 0
        new_pages = sorted(set((existing.pages or []) + (assessment.pages or [])))
        if new_rank > existing_rank:
            merged[check_id] = assessment
            merged[check_id].pages = new_pages
        else:
            existing.pages = new_pages


def _parse_checklist_batch_result(content: Any) -> ChecklistBatchResult:
    if isinstance(content, ChecklistBatchResult):
        return content
    if isinstance(content, list):
        return ChecklistBatchResult.model_validate(
            {"assessments": [_normalize_assessment_payload(item) for item in content]}
        )
    if isinstance(content, dict):
        content = dict(content)
        if "assessments" in content:
            if isinstance(content["assessments"], list):
                content["assessments"] = [_normalize_assessment_payload(item) for item in content["assessments"]]
            return ChecklistBatchResult.model_validate(content)
        return ChecklistBatchResult.model_validate({"assessments": [_normalize_assessment_payload(content)]})
    if isinstance(content, str):
        content = _extract_json_payload_text(content)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            return ChecklistBatchResult.model_validate_json(content)
        return _parse_checklist_batch_result(decoded)
    return ChecklistBatchResult.model_validate(content)


def _normalize_assessment_payload(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    if "status" not in normalized and "assessment" in normalized:
        normalized["status"] = normalized.pop("assessment")
    return normalized


def _extract_json_payload_text(text: str) -> str:
    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    object_start = stripped.find("{")
    array_start = stripped.find("[")
    candidates = [index for index in (object_start, array_start) if index >= 0]
    if not candidates:
        return stripped
    start = min(candidates)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if end <= start:
        return stripped
    return stripped[start : end + 1]


def _build_vision_definition_batches(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
    visual_page_index: VisualPageIndex,
    figure_table_assets: list[FigureTableAsset] | None = None,
) -> list[DefinitionBatch]:
    grouped: dict[str, list[ChecklistDefinition]] = defaultdict(list)
    for definition in definitions:
        grouped[_definition_group_label(definition)].append(definition)

    batches: list[DefinitionBatch] = []
    for label, grouped_definitions in grouped.items():
        if _definitions_target_figure_table_assets(grouped_definitions) and figure_table_assets:
            asset_chunks = _chunked(
                sorted(
                    [asset for asset in figure_table_assets if asset.image_path],
                    key=lambda asset: (asset.pdf_page, asset.caption_bbox[1], asset.caption_bbox[0], asset.kind),
                ),
                max(1, settings.max_visual_images_per_batch),
            )
            for asset_index, asset_chunk in enumerate(asset_chunks, start=1):
                page_numbers = sorted({asset.pdf_page for asset in asset_chunk})
                for definition_batch in _chunked(grouped_definitions, settings.max_check_items_per_batch):
                    batches.append(
                        DefinitionBatch(
                            label=f"{label} / 图表截图批次 {asset_index}",
                            page_numbers=page_numbers,
                            definitions=definition_batch,
                            asset_keys=[_figure_table_asset_key(asset) for asset in asset_chunk],
                        )
                    )
            continue

        page_numbers = sorted(
            _collect_vision_batch_page_candidates(
                grouped_definitions,
                pages,
                visual_page_index,
                settings.max_visual_images_per_batch,
                max_total=settings.max_visual_images_per_batch,
            )
        )
        for definition_batch in _chunked(grouped_definitions, settings.max_check_items_per_batch):
            batches.append(
                DefinitionBatch(
                    label=label,
                    page_numbers=page_numbers,
                    definitions=definition_batch,
                )
            )
    return batches


def _definition_group_label(definition: ChecklistDefinition) -> str:
    parts = definition.source_section.split(" / ")
    if len(parts) >= 2:
        return parts[1]
    return parts[0]


def _extract_vision_figure_table_assets(
    definitions: list[ChecklistDefinition],
    pdf_path: Path,
    temp_path: Path,
) -> list[FigureTableAsset] | None:
    if not _definitions_target_figure_table_assets(definitions) or not pdf_path.exists():
        return None
    try:
        return extract_figure_table_assets(pdf_path, temp_path / "figure-table-assets")
    except Exception as exc:
        logger.warning("figure/table asset extraction failed for vision checks: %s", exc)
        return None


def _definitions_target_figure_table_assets(definitions: list[ChecklistDefinition]) -> bool:
    return any(
        _targets_figure_table_visuals(f"{definition.source_section} {definition.requirement}")
        for definition in definitions
    )


def _run_local_segment_reviews(
    pages: list[ExtractedPage],
    runtime_context: AnalysisRuntimeContext | None,
) -> list[SegmentReviewEnvelope]:
    if not pages:
        return []

    batch_size = max(1, settings.local_review_page_batch_size)
    reviews: list[SegmentReviewEnvelope] = []
    for segment_pages in _chunk_pages(pages, batch_size):
        prompt = _build_local_segment_prompt(segment_pages)
        try:
            response = _run_agent_with_tracking(
                phase="local_segment_review",
                prompt=prompt,
                runtime_context=runtime_context,
                request_group=f"PDF {segment_pages[0].number}-{segment_pages[-1].number}",
                page_numbers=[page.number for page in segment_pages],
                metadata={"page_count": len(segment_pages)},
                agent_getter=get_local_segment_reviewer_agent,
            )
            content = response.content
            review = (
                content if isinstance(content, LocalSegmentReview) else LocalSegmentReview.model_validate_json(content)
            )
        except Exception as exc:
            logger.warning(
                "Local segment review failed for PDF pages %s-%s: %s",
                segment_pages[0].number,
                segment_pages[-1].number,
                exc,
            )
            review = LocalSegmentReview(
                summary="该分段局部复核未能完整生成，建议结合逐项清单和原文继续人工复核。",
                logic_risks=["局部摘要生成失败，分段逻辑风险需人工确认"],
            )
        reviews.append(
            SegmentReviewEnvelope(
                page_start=segment_pages[0].number,
                page_end=segment_pages[-1].number,
                review=review,
            )
        )
    return reviews


def _build_local_segment_prompt(segment_pages: list[ExtractedPage]) -> str:
    start_page = segment_pages[0].number
    end_page = segment_pages[-1].number
    page_lines = [_format_segment_page_snippet(page) for page in segment_pages]
    parts = [
        "\n\n".join(page_lines),
        "Review the local thesis segment above.",
        "This is a page-by-page synopsis built from excerpted snippets, not the full verbatim chapter text.",
        "Do not check sentence-level wording. Focus on local logic, section flow, evidence support, repeated discussion, undefined concepts, and abrupt transitions.",
        f"Segment range: PDF pages {start_page}-{end_page}.",
    ]
    return "\n\n".join(parts)


def _build_global_summary(
    pages: list[ExtractedPage],
    local_segment_reviews: list[SegmentReviewEnvelope],
    checks: list[AnalysisCheck],
    runtime_context: AnalysisRuntimeContext | None,
) -> str | None:
    if not pages:
        return None

    prompt = _build_global_review_prompt(pages, local_segment_reviews, checks)
    try:
        response = _run_agent_with_tracking(
            phase="global_summary_review",
            prompt=prompt,
            runtime_context=runtime_context,
            request_group="global_summary",
            page_numbers=[page.number for page in pages],
            metadata={"page_count": len(pages), "check_count": len(checks)},
            agent_getter=get_global_synopsis_reviewer_agent,
        )
        content = response.content
        parsed = (
            content if isinstance(content, GlobalSynopsisReview) else GlobalSynopsisReview.model_validate_json(content)
        )
    except Exception as exc:
        logger.warning("Global synopsis review failed: %s", exc)
        return "全文梗概复核未能完整生成，建议结合分段检查结果人工确认整体逻辑闭环。"

    details: list[str] = [parsed.summary.strip()]
    if parsed.consistency_findings:
        details.append("一致性关注：" + "；".join(parsed.consistency_findings[:3]))
    if parsed.next_focus:
        details.append("建议优先关注：" + "；".join(parsed.next_focus[:3]))
    return " ".join(part for part in details if part).strip()


def _build_text_batch_prompt(batch: DefinitionBatch, pages: list[ExtractedPage]) -> str:
    snippet_lines = [_format_page_snippet(page) for page in pages if page.number in batch.page_numbers]
    parts: list[str] = ["\n\n".join(snippet_lines)]
    checklist_lines: list[str] = []
    for item in batch.definitions:
        checklist_lines.append(
            f"- check_id: {item.check_id}\n  section: {item.source_section}\n  severity: {item.severity}\n  requirement: {item.requirement}"
        )
        if item.examples:
            example_text = "\n    - ".join([""] + list(item.examples[:3]))
            checklist_lines.append(f"  expert_comment_examples:{example_text}")
    parts.append("Review the thesis checklist items against the document snippets above.")
    if batch.label.startswith("PDF pages"):
        parts.append(f"Review scope: {batch.label}.")
    else:
        parts.append(f"Primary review direction: {batch.label}.")
    parts.append("Only use the provided snippets. If the evidence is insufficient, return `needs_manual_review`.")
    parts.append(
        "Expert comment examples are illustrative: use them to understand what kind of problems to look for, but judge the current thesis on its own evidence."
    )
    parts.append("Checklist items:\n" + "\n".join(checklist_lines))
    parts.append(
        "Important: the `pages` field in your structured response must use PDF page numbers, not thesis printed page numbers."
    )
    return "\n\n".join(parts)


def _build_vision_batch_prompt(
    batch: DefinitionBatch,
    pages: list[ExtractedPage],
    rendered: VisionBatchImages | None = None,
) -> str:
    snippet_lines = [_format_page_snippet(page) for page in pages if page.number in batch.page_numbers]
    parts: list[str] = ["\n\n".join(snippet_lines)]
    checklist_lines = [
        f"- check_id: {item.check_id}\n  section: {item.source_section}\n  severity: {item.severity}\n  requirement: {item.requirement}"
        for item in batch.definitions
    ]
    parts.append(
        "Review the visual checklist items against the document snippets above and the attached thesis page or figure/table images."
    )
    parts.append(f"Primary review direction: {batch.label}.")
    if rendered and rendered.image_context:
        parts.append("Attached image order:\n" + "\n".join(rendered.image_context))
        if rendered.source == "figure_table_assets":
            parts.append(
                "重要：这些图表图片来自自动裁剪，可能包含相邻正文、公式或页码，也可能略微超出图表边界。"
                "判断时请以图表标题、图表主体、编号和标题位置为依据，不要把裁剪上下文直接视为论文本身的违规。"
                "如果自动裁剪缺少关键图表内容，请返回 `needs_manual_review`，并说明需要复核原始页面。"
            )
    else:
        parts.append(
            f"The attached images correspond to pages in this order: {', '.join(_format_page_reference(page, pages) for page in batch.page_numbers)}."
        )
    parts.append("Use `needs_manual_review` if the images still do not provide enough evidence.")
    parts.append("Checklist items:\n" + "\n".join(checklist_lines))
    parts.append(
        "Important: return exactly one assessment for every listed check_id, and copy each check_id exactly as provided."
    )
    parts.append(
        "Important: the `pages` field in your structured response must use PDF page numbers, not thesis printed page numbers."
    )
    return "\n\n".join(parts)


def _render_vision_batch_images(
    pdf_path: Path,
    batch: DefinitionBatch,
    pages: list[ExtractedPage],
    output_dir: Path,
    figure_table_assets: list[FigureTableAsset] | None = None,
) -> VisionBatchImages:
    if _batch_targets_figure_table_assets(batch) and pdf_path.exists():
        try:
            assets = figure_table_assets
            if assets is None:
                assets = extract_figure_table_assets(pdf_path, output_dir / "figure-table-assets")
            selected_assets = _select_figure_table_assets_for_batch(assets, batch.page_numbers, batch.asset_keys)
            images = [
                Image(filepath=Path(asset.image_path), detail="high")
                for asset in selected_assets
                if asset.image_path is not None
            ]
            if images:
                return VisionBatchImages(
                    images=images,
                    image_context=[
                        _format_asset_image_context(index, asset, pages)
                        for index, asset in enumerate(selected_assets, start=1)
                        if asset.image_path is not None
                    ],
                    source="figure_table_assets",
                )
        except Exception as exc:
            logger.warning("figure/table asset extraction failed for vision batch %s: %s", batch.label, exc)

    images = _render_pages_to_images(pdf_path, batch.page_numbers, output_dir)
    return VisionBatchImages(
        images=images,
        image_context=[
            f"{index}. {_format_page_reference(page_number, pages)}"
            for index, page_number in enumerate(batch.page_numbers, start=1)
        ],
        source="page_images",
    )


def _batch_targets_figure_table_assets(batch: DefinitionBatch) -> bool:
    return any(
        _targets_figure_table_visuals(f"{definition.source_section} {definition.requirement}")
        for definition in batch.definitions
    )


def _select_figure_table_assets_for_batch(
    assets: list[FigureTableAsset],
    page_numbers: list[int],
    asset_keys: list[str] | None = None,
) -> list[FigureTableAsset]:
    if asset_keys:
        key_set = set(asset_keys)
        selected = [asset for asset in assets if _figure_table_asset_key(asset) in key_set and asset.image_path]
    else:
        page_set = set(page_numbers)
        selected = [asset for asset in assets if asset.pdf_page in page_set and asset.image_path]
    selected.sort(key=lambda asset: (asset.pdf_page, asset.caption_bbox[1], asset.caption_bbox[0], asset.kind))
    if asset_keys:
        return selected
    max_assets = max(settings.max_visual_images_per_batch, 1)
    return selected[:max_assets]


def _figure_table_asset_key(asset: FigureTableAsset) -> str:
    return f"{asset.kind}:{asset.label}:page:{asset.pdf_page}:caption:{asset.caption_bbox}"


def _format_asset_image_context(index: int, asset: FigureTableAsset, pages: list[ExtractedPage]) -> str:
    kind_name = "图截图" if asset.kind == "figure" else "表截图"
    position_text = {
        "above": "标题在主体上方",
        "below": "标题在主体下方",
        "overlap": "标题与主体区域重叠",
        "unknown": "标题与主体位置未知",
    }[asset.caption_position]
    return (
        f"{index}. {kind_name}: {asset.label} {asset.title}；"
        f"{_format_page_reference(asset.pdf_page, pages)}；{position_text}；抽取方式: {asset.detection_method}"
    )


def _build_global_review_prompt(
    pages: list[ExtractedPage],
    local_segment_reviews: list[SegmentReviewEnvelope],
    checks: list[AnalysisCheck],
) -> str:
    parts = [
        _build_global_anchor_snippets(pages),
        "Review the whole thesis at a global level.",
        "The input below is a synopsis of the thesis, not the full verbatim text.",
        "Do not inspect exact wording or line-level style. Focus only on overall logic, chapter coherence, consistency of contributions, method-experiment-conclusion alignment, and cross-section contradictions.",
        "Document outline:\n" + _build_document_outline(pages),
    ]
    parts.append("Local segment reviews:\n" + _build_local_review_digest(local_segment_reviews))
    parts.append("Primary checklist digest:\n" + _build_primary_check_digest(checks))
    return "\n\n".join(parts)


def _collect_batch_page_candidates(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
    limit_per_item: int,
    max_total: int | None = None,
) -> list[int]:
    selected: list[int] = []
    for definition in definitions:
        for page_number in _select_relevant_pages(definition, pages, limit_per_item):
            if page_number not in selected:
                selected.append(page_number)
            if max_total is not None and len(selected) >= max_total:
                return selected
    return selected


def _collect_vision_batch_page_candidates(
    definitions: list[ChecklistDefinition],
    pages: list[ExtractedPage],
    visual_page_index: VisualPageIndex,
    limit_per_item: int,
    max_total: int | None = None,
) -> list[int]:
    selected: list[int] = []
    for definition in definitions:
        for page_number in _select_visual_relevant_pages(
            definition,
            pages,
            visual_page_index,
            limit_per_item,
        ):
            if page_number not in selected:
                selected.append(page_number)
            if max_total is not None and len(selected) >= max_total:
                return selected
    return selected


def _select_relevant_pages(
    definition: ChecklistDefinition,
    pages: list[ExtractedPage],
    limit: int,
) -> list[int]:
    combined = f"{definition.source_section} {definition.requirement}"
    keywords = extract_query_terms(combined)

    if "摘要" in combined:
        keywords.extend(["摘要", "Abstract"])
    if "参考文献" in combined:
        keywords.extend(["参考文献", "[1]"])
    if "图" in combined or "表" in combined:
        keywords.extend(["图", "表", "如图", "如表"])
    if "页眉" in combined or "页脚" in combined:
        return [page.number for page in pages[: min(limit, len(pages))]]

    scores: list[tuple[int, int]] = []
    for page in pages:
        score = 0
        for keyword in keywords:
            if len(keyword) == 1 and keyword not in {"图", "表"}:
                continue
            score += page.text.count(keyword)
        if score > 0:
            scores.append((score, page.number))

    if not scores:
        if any(token in combined for token in ("创新", "工作量", "技术深度", "实际应用场景", "相关工作")):
            return _sample_document_pages(pages, limit)
        return [page.number for page in pages[: min(limit, len(pages))]]

    scores.sort(key=lambda item: (-item[0], item[1]))
    return [page_number for _, page_number in scores[:limit]]


def _select_visual_relevant_pages(
    definition: ChecklistDefinition,
    pages: list[ExtractedPage],
    visual_page_index: VisualPageIndex,
    limit: int,
) -> list[int]:
    combined = f"{definition.source_section} {definition.requirement}"

    if "页眉" in combined or "页脚" in combined:
        return _sample_document_pages(pages, limit)

    if _targets_figure_table_visuals(combined):
        figure_table_pages = _rank_pages_by_keywords(
            pages,
            visual_page_index.candidate_pages,
            _build_visual_query_terms(combined),
            caption_pages=visual_page_index.caption_pages,
            reference_pages=visual_page_index.reference_pages,
            image_pages=visual_page_index.image_pages,
        )
        if figure_table_pages:
            return figure_table_pages[:limit]

    return _select_relevant_pages(definition, pages, limit)


def _targets_figure_table_visuals(combined: str) -> bool:
    figure_table_keywords = (
        "图表",
        "图的",
        "表格",
        "坐标",
        "单位",
        "清晰度",
        "模糊",
        "标题放在图的下方",
        "标题放在表的上方",
        "不要跨页",
        "页面宽度",
        "布局",
        "字体",
        "对齐",
        "图中文字",
        "框架图",
        "流程图",
        "时序图",
        "顺序图",
        "泳道图",
    )
    return any(keyword in combined for keyword in figure_table_keywords)


def _build_visual_query_terms(combined: str) -> list[str]:
    keywords = extract_query_terms(combined)
    keywords.extend(["图", "表", "如图", "如表", "Figure", "Fig", "Table"])
    deduped: list[str] = []
    for keyword in keywords:
        if keyword not in deduped:
            deduped.append(keyword)
    return deduped


def _rank_pages_by_keywords(
    pages: list[ExtractedPage],
    candidate_pages: list[int],
    keywords: list[str],
    *,
    caption_pages: list[int] | None = None,
    reference_pages: list[int] | None = None,
    image_pages: list[int] | None = None,
) -> list[int]:
    if not candidate_pages:
        return []

    page_lookup = {page.number: page for page in pages}
    caption_page_set = set(caption_pages or [])
    reference_page_set = set(reference_pages or [])
    image_page_set = set(image_pages or [])
    scored_pages: list[tuple[int, int]] = []
    for page_number in candidate_pages:
        page = page_lookup.get(page_number)
        if page is None:
            continue

        score = 0
        for keyword in keywords:
            if len(keyword) == 1 and keyword not in {"图", "表"}:
                continue
            score += page.text.count(keyword)
        if page_number in caption_page_set:
            score += 6
        if page_number in image_page_set:
            score += 4
        if page_number in reference_page_set:
            score += 2
        scored_pages.append((score, page_number))

    scored_pages.sort(key=lambda item: (-item[0], item[1]))
    return [page_number for _, page_number in scored_pages]


def _sample_document_pages(pages: list[ExtractedPage], limit: int) -> list[int]:
    if len(pages) <= limit:
        return [page.number for page in pages]
    positions = {0, len(pages) // 4, len(pages) // 2, (3 * len(pages)) // 4, len(pages) - 1}
    sampled = [pages[index].number for index in sorted(positions)]
    return sampled[:limit]


def _format_page_snippet(page: ExtractedPage) -> str:
    text = page.text
    if settings.max_page_chars and len(text) > settings.max_page_chars:
        text = text[: settings.max_page_chars].rstrip() + "..."
    return f"{_page_prompt_prefix(page)}:\n{text}"


def _format_segment_page_snippet(page: ExtractedPage) -> str:
    text = page.text
    limit = settings.segment_review_page_chars
    if limit > 0 and len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return f"{_page_prompt_prefix(page)}:\n{text}"


def _page_prompt_prefix(page: ExtractedPage) -> str:
    if page.document_page_label:
        return f"PDF Page {page.number} / Thesis Page {page.document_page_label}"
    return f"PDF Page {page.number}"


def _format_page_reference(pdf_page: int, pages: list[ExtractedPage]) -> str:
    page = next((item for item in pages if item.number == pdf_page), None)
    if page is None:
        return f"PDF Page {pdf_page}"
    return _page_prompt_prefix(page)


def _render_pages_to_images(pdf_path: Path, page_numbers: list[int], output_dir: Path) -> list[Image]:
    doc = fitz.open(str(pdf_path))
    images: list[Image] = []
    try:
        for page_number in page_numbers:
            page = doc.load_page(page_number - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_path = output_dir / f"page-{page_number}.png"
            pix.save(image_path)
            images.append(Image(filepath=image_path, detail="high"))
    finally:
        doc.close()
    return images


def _chunk_pages(pages: list[ExtractedPage], size: int) -> list[list[ExtractedPage]]:
    if size <= 0:
        return [pages]
    return [pages[index : index + size] for index in range(0, len(pages), size)]


def _build_document_outline(pages: list[ExtractedPage]) -> str:
    outline_lines: list[str] = []
    seen: set[tuple[int, str]] = set()
    heading_pattern = re.compile(r"^(第[一二三四五六七八九十百]+章.*|\d+(?:\.\d+){0,2}\s+\S.*)$")
    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if heading_pattern.match(stripped):
                entry = (page.number, stripped)
                if entry not in seen:
                    seen.add(entry)
                    outline_lines.append(f"{_format_page_reference(page.number, pages)}: {stripped}")
                break
    if not outline_lines:
        return "No reliable heading outline was extracted."
    return "\n".join(outline_lines[:24])


def _build_global_anchor_snippets(pages: list[ExtractedPage]) -> str:
    anchor_keywords = (
        "摘要",
        "Abstract",
        "绪论",
        "结论",
        "研究结论",
        "创新",
        "参考文献",
    )
    lines: list[str] = []
    for page in pages:
        if not any(keyword in page.text for keyword in anchor_keywords):
            continue
        text = page.text
        limit = settings.global_anchor_page_chars
        if limit > 0 and len(text) > limit:
            text = text[:limit].rstrip() + "..."
        lines.append(f"{_page_prompt_prefix(page)}:\n{text}")
    if not lines:
        sampled = _sample_document_pages(pages, min(5, len(pages)))
        for page_number in sampled:
            page = next((item for item in pages if item.number == page_number), None)
            if page is None:
                continue
            text = page.text
            limit = settings.global_anchor_page_chars
            if limit > 0 and len(text) > limit:
                text = text[:limit].rstrip() + "..."
            lines.append(f"{_page_prompt_prefix(page)}:\n{text}")
    return "\n\n".join(lines[:8])


def _build_local_review_digest(local_segment_reviews: list[SegmentReviewEnvelope]) -> str:
    if not local_segment_reviews:
        return "No local segment reviews were produced."

    lines: list[str] = []
    for item in local_segment_reviews:
        line = f"Segment PDF pages {item.page_start}-{item.page_end}: {item.review.summary}"
        if item.review.logic_risks:
            line += " Risks: " + "；".join(item.review.logic_risks[:3])
        lines.append(line)
    return "\n".join(lines)


def _build_primary_check_digest(checks: list[AnalysisCheck]) -> str:
    primary_checks = [check for check in checks if check.layer != "vision_model"]
    failed_checks = [check for check in primary_checks if check.status == "failed"]
    manual_checks = [check for check in primary_checks if check.status == "needs_manual_review"]

    parts = [
        f"Primary checks total: {len(primary_checks)}.",
        f"Failed: {len(failed_checks)}.",
        f"Needs manual review: {len(manual_checks)}.",
    ]
    highlighted = failed_checks[:5] + manual_checks[:3]
    if highlighted:
        parts.append("Highlights: " + " | ".join(f"{check.title}: {check.rationale}" for check in highlighted))
    return " ".join(parts)


def _build_llm_usage_summary(calls: list[LLMCallTrace]) -> AnalysisLLMUsageSummary:
    if not calls:
        return AnalysisLLMUsageSummary()

    phase_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_read_tokens": 0,
            "total_duration_ms": 0,
        }
    )

    completed_calls = 0
    failed_calls = 0
    total_input_chars = 0
    total_output_chars = 0
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    reasoning_tokens = 0
    total_duration_ms = 0

    for call in calls:
        phase_totals[call.phase]["calls"] += 1
        phase_totals[call.phase]["input_tokens"] += call.input_tokens
        phase_totals[call.phase]["output_tokens"] += call.output_tokens
        phase_totals[call.phase]["total_tokens"] += call.total_tokens
        phase_totals[call.phase]["cache_read_tokens"] += call.cache_read_tokens
        phase_totals[call.phase]["total_duration_ms"] += call.duration_ms

        total_input_chars += call.input_chars
        total_output_chars += call.output_chars
        input_tokens += call.input_tokens
        output_tokens += call.output_tokens
        total_tokens += call.total_tokens
        cache_read_tokens += call.cache_read_tokens
        cache_write_tokens += call.cache_write_tokens
        reasoning_tokens += call.reasoning_tokens
        total_duration_ms += call.duration_ms
        if call.status == "completed":
            completed_calls += 1
        else:
            failed_calls += 1

    estimated_cache_hit_rate = None
    if input_tokens > 0:
        estimated_cache_hit_rate = round(cache_read_tokens / input_tokens, 4)

    phases = [
        AnalysisLLMUsagePhaseSummary(
            phase=phase,
            calls=values["calls"],
            input_tokens=values["input_tokens"],
            output_tokens=values["output_tokens"],
            total_tokens=values["total_tokens"],
            cache_read_tokens=values["cache_read_tokens"],
            total_duration_ms=values["total_duration_ms"],
        )
        for phase, values in sorted(phase_totals.items())
    ]

    return AnalysisLLMUsageSummary(
        total_calls=len(calls),
        completed_calls=completed_calls,
        failed_calls=failed_calls,
        total_input_chars=total_input_chars,
        total_output_chars=total_output_chars,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
        total_duration_ms=total_duration_ms,
        average_duration_ms=(total_duration_ms // len(calls)),
        estimated_cache_hit_rate=estimated_cache_hit_rate,
        phases=phases,
    )


def _persist_llm_telemetry(
    db,
    task: AnalysisTask,
    runtime_context: AnalysisRuntimeContext,
) -> None:
    summary = _build_llm_usage_summary(runtime_context.llm_calls)
    task.llm_usage_summary_json = summary.model_dump()

    db.query(AnalysisLLMCallLog).filter(AnalysisLLMCallLog.analysis_task_id == task.id).delete()
    for index, call in enumerate(runtime_context.llm_calls, start=1):
        db.add(
            AnalysisLLMCallLog(
                analysis_task_id=task.id,
                phase=call.phase,
                call_index=index,
                request_group=call.request_group,
                status=call.status,
                prompt_hash=call.prompt_hash,
                prompt_prefix_hash=call.prompt_prefix_hash,
                prompt_prefix_chars=call.prompt_prefix_chars,
                input_chars=call.input_chars,
                output_chars=call.output_chars,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                total_tokens=call.total_tokens,
                cache_read_tokens=call.cache_read_tokens,
                cache_write_tokens=call.cache_write_tokens,
                reasoning_tokens=call.reasoning_tokens,
                duration_ms=call.duration_ms,
                time_to_first_token_ms=call.time_to_first_token_ms,
                cost=call.cost,
                model_id=call.model_id,
                model_provider=call.model_provider,
                error_message=call.error_message,
                check_ids_json=call.check_ids,
                page_numbers_json=call.page_numbers,
                metrics_json=call.metrics,
                metadata_json=call.metadata,
            )
        )


def _build_issues(checks: list[AnalysisCheck]) -> list[AnalysisIssue]:
    issues: list[AnalysisIssue] = []
    seen: set[tuple[str, int, str, str]] = set()
    for check in checks:
        if check.status != "failed":
            continue
        page_index = _select_issue_page_index(check)
        issue_page = check.pages[page_index] if check.pages else 1
        key = (
            check.check_id,
            issue_page,
            check.title,
            check.rationale,
        )
        if key in seen:
            continue
        seen.add(key)
        issues.append(
            AnalysisIssue(
                page=key[1],
                page_label=(check.page_labels[page_index] if page_index < len(check.page_labels) else None),
                pdf_page=(check.pdf_pages[page_index] if page_index < len(check.pdf_pages) else None),
                issue_type=check.title,
                severity=check.severity,
                description=check.rationale,
                suggestion=check.suggestion,
            )
        )
    return issues


def _select_issue_page_index(check: AnalysisCheck) -> int:
    if not check.pages:
        return 0

    pdf_mentions = [int(value) for value in re.findall(r"PDF\s*第\s*(\d+)\s*页", check.rationale)]
    for pdf_page in pdf_mentions:
        if pdf_page in check.pdf_pages:
            return check.pdf_pages.index(pdf_page)

    page_mentions = [value for value in re.findall(r"(?<!PDF)第\s*([A-Za-z]?\d+|[IVXLCDM]+)\s*页", check.rationale)]
    normalized_labels = [label.strip() for label in check.page_labels]
    for mentioned in page_mentions:
        if mentioned in normalized_labels:
            return normalized_labels.index(mentioned)

    return 0


def _apply_page_mapping_to_checks(checks: list[AnalysisCheck], pages: list[ExtractedPage]) -> list[AnalysisCheck]:
    page_lookup = {page.number: page for page in pages}
    mapped_checks: list[AnalysisCheck] = []
    for check in checks:
        pdf_pages = sorted(set(page for page in check.pages if page in page_lookup))
        page_refs = [page_lookup[pdf_page] for pdf_page in pdf_pages]
        mapped_checks.append(
            check.model_copy(
                update={
                    "pages": [_display_page_number(page) for page in page_refs],
                    "page_labels": [_display_page_label(page) for page in page_refs],
                    "pdf_pages": pdf_pages,
                }
            )
        )
    return mapped_checks


def _display_page_number(page: ExtractedPage) -> int:
    return page.document_page_number or page.number


def _display_page_label(page: ExtractedPage) -> str:
    return page.document_page_label or f"PDF {page.number}"


def _build_layer_summaries(checks: list[AnalysisCheck]) -> list[AnalysisLayerSummary]:
    summaries: list[AnalysisLayerSummary] = []
    for layer in ("rule", "text_model", "vision_model"):
        layer_checks = [check for check in checks if check.layer == layer]
        counter = Counter(check.status for check in layer_checks)
        summaries.append(
            AnalysisLayerSummary(
                layer=layer,
                total=len(layer_checks),
                passed=counter.get("passed", 0),
                failed=counter.get("failed", 0),
                needs_manual_review=counter.get("needs_manual_review", 0),
            )
        )
    return summaries


def _build_summary(checks: list[AnalysisCheck], layer_summaries: list[AnalysisLayerSummary]) -> str:
    primary_checks = [check for check in checks if check.layer != "vision_model"]
    total = len(primary_checks)
    failed = sum(check.status == "failed" for check in primary_checks)
    passed = sum(check.status == "passed" for check in primary_checks)
    manual = sum(check.status == "needs_manual_review" for check in primary_checks)
    layer_parts = []
    for summary in layer_summaries:
        if summary.total == 0 or summary.layer == "vision_model":
            continue
        layer_label = {"rule": "规则层", "text_model": "文本模型层", "vision_model": "视觉模型层"}.get(
            summary.layer, summary.layer
        )
        layer_parts.append(f"{layer_label}: {summary.passed}/{summary.total} 通过")
    return (
        f"正文主检查共覆盖 {total} 条规范，{passed} 条通过，{failed} 条未通过，{manual} 条需人工复核。"
        f" 分层结果为：{'; '.join(layer_parts)}。"
    )


def _build_overall_assessment(failed_count: int, manual_count: int) -> str:
    if failed_count == 0 and manual_count == 0:
        return "整体符合当前参考规范，未发现明确问题。"
    if failed_count == 0:
        return "未发现明确违规项，但仍有部分条目需要人工复核。"
    if failed_count <= 5:
        return "存在少量明确问题，建议先按清单逐项修改。"
    return "存在较多明确问题，建议按清单分层整改后再提交导师评审。"


def _build_visual_summary(checks: list[AnalysisCheck]) -> str | None:
    visual_checks = [check for check in checks if check.layer == "vision_model"]
    if not visual_checks:
        return None

    total = len(visual_checks)
    passed = sum(check.status == "passed" for check in visual_checks)
    failed = sum(check.status == "failed" for check in visual_checks)
    manual = sum(check.status == "needs_manual_review" for check in visual_checks)
    return f"图表视觉复核共覆盖 {total} 条规范，{passed} 条通过，{failed} 条未通过，{manual} 条需人工复核。"


def _fallback_check(
    definition: ChecklistDefinition,
    status: str,
    rationale: str,
    suggestion: str,
) -> AnalysisCheck:
    return AnalysisCheck(
        check_id=definition.check_id,
        title=definition.title,
        source_section=definition.source_section,
        requirement=definition.requirement,
        layer=definition.layer,
        severity=definition.severity,
        status=status,  # type: ignore[arg-type]
        rationale=rationale,
        suggestion=suggestion,
        pages=[],
    )


def _chunked(items: list[ChecklistDefinition], size: int) -> list[list[ChecklistDefinition]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def _to_user_facing_error(exc: Exception) -> str:
    message = str(exc)
    if "OPENAI_API_KEY not set" in message:
        return "本次分析暂未完成，请稍后重试。"
    if isinstance(exc, FileNotFoundError):
        return "未找到论文文件，请重新上传后再试。"
    if "超过当前分析上限" in message:
        return message
    if isinstance(exc, (ValueError,)):
        return "论文文件无法正常解析，请确认上传的是可读取的 PDF。"
    return "本次分析暂未完成，请稍后重试。"


def run_analysis_task(task_id: int) -> None:
    db = SessionLocal()
    runtime_context = AnalysisRuntimeContext(analysis_task_id=task_id)
    try:
        task = db.get(AnalysisTask, task_id)
        if not task:
            return

        task.status = ANALYSIS_STATUS_RUNNING
        task.started_at = utcnow()
        db.commit()

        version = task.version
        if not version:
            raise RuntimeError("Missing thesis version for analysis task.")

        result = analyze_pdf(version.file_path, runtime_context=runtime_context)
        task.result_json = result.model_dump()
        _persist_llm_telemetry(db, task, runtime_context)
        task.status = ANALYSIS_STATUS_COMPLETED
        task.finished_at = utcnow()

        thesis = version.thesis
        if thesis:
            thesis.status = THESIS_STATUS_ANALYSIS_DONE

            notification = Notification(
                user_id=thesis.student_id,
                title="Draft review completed",
                body="Your draft review is ready in the system.",
                is_read=False,
            )
            db.add(notification)

        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analysis task %s failed", task_id)
        task = db.get(AnalysisTask, task_id)
        if task:
            _persist_llm_telemetry(db, task, runtime_context)
            task.status = ANALYSIS_STATUS_FAILED
            task.error_message = _to_user_facing_error(exc)
            task.finished_at = utcnow()
            db.commit()
    finally:
        db.close()
