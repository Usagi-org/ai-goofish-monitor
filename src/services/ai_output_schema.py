"""Provider-compatible strict output schemas and local result validation."""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Criterion(StrictOutput):
    status: Literal["PASS", "FAIL", "NEEDS_MANUAL_CHECK"]
    comment: str
    evidence: str


class SellerCriterion(Criterion):
    persona: str


class CriteriaAnalysis(StrictOutput):
    product_fit: Criterion
    condition: Criterion
    seller_type: SellerCriterion
    price_value: Criterion


class AnalysisResult(StrictOutput):
    prompt_version: str
    is_recommended: bool
    reason: str
    risk_tags: list[str]
    criteria_analysis: CriteriaAnalysis
    value_score: float | None
    value_summary: str | None


class GeneratedCriteria(StrictOutput):
    criteria: str


ANALYSIS_SCHEMA = AnalysisResult.model_json_schema()
CRITERIA_SCHEMA = GeneratedCriteria.model_json_schema()
