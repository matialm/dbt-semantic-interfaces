from __future__ import annotations

import enum
import re
from typing import Dict, List, Optional, Sequence, Tuple

from dbt_semantic_interfaces.enum_extension import assert_values_exhausted
from dbt_semantic_interfaces.protocols.semantic_manifest import SemanticManifest
from dbt_semantic_interfaces.protocols.semantic_model import SemanticModel
from dbt_semantic_interfaces.references import (
    ElementReference,
    MetricModelReference,
    SemanticModelElementReference,
    SemanticModelReference,
)
from dbt_semantic_interfaces.type_enums.time_granularity import TimeGranularity
from dbt_semantic_interfaces.validations.validator_helpers import (
    FileContext,
    MetricContext,
    ModelValidationRule,
    SemanticModelContext,
    SemanticModelElementContext,
    SemanticModelElementType,
    ValidationContext,
    ValidationError,
    ValidationIssue,
    validate_safely,
)


@enum.unique
class MetricFlowReservedKeywords(enum.Enum):
    """Enumeration of reserved keywords with helper for accessing the reason they are reserved."""

    METRIC_TIME = "metric_time"
    MF_INTERNAL_UUID = "mf_internal_uuid"

    @staticmethod
    def get_reserved_reason(keyword: MetricFlowReservedKeywords) -> str:
        """Get the reason a given keyword is reserved. Guarantees an exhaustive switch."""
        if keyword is MetricFlowReservedKeywords.METRIC_TIME:
            return (
                "Used as the query input for creating time series metrics from measures with "
                "different time dimension names."
            )
        elif keyword is MetricFlowReservedKeywords.MF_INTERNAL_UUID:
            return "Used internally to reference a column that has a uuid generated by MetricFlow."
        else:
            assert_values_exhausted(keyword)


class UniqueAndValidNameRule(ModelValidationRule):
    """Check that names are unique and valid.

    * Names of elements in semantic models are unique / valid within the semantic model.
    * Names of semantic models, dimension sets and metric sets in the model are unique / valid.
    """

    NAME_REGEX = re.compile(r"\A[a-z][a-z0-9_]*[a-z0-9]\Z")

    @staticmethod
    def check_valid_name(name: str, context: Optional[ValidationContext] = None) -> List[ValidationIssue]:  # noqa: D
        issues: List[ValidationIssue] = []

        if not UniqueAndValidNameRule.NAME_REGEX.match(name):
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - names should only consist of lower case letters, numbers, "
                    f"and underscores. In addition, names should start with a lower case letter, and should not end "
                    f"with an underscore, and they must be at least 2 characters long.",
                )
            )
        if name.upper() in TimeGranularity.list_names():
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - names cannot match reserved time granularity keywords "
                    f"({TimeGranularity.list_names()})",
                )
            )
        if name.lower() in {reserved_name.value for reserved_name in MetricFlowReservedKeywords}:
            reason = MetricFlowReservedKeywords.get_reserved_reason(MetricFlowReservedKeywords(name.lower()))
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - this name is reserved by MetricFlow. Reason: {reason}",
                )
            )
        return issues

    @staticmethod
    @validate_safely(whats_being_done="checking semantic model sub element names are unique")
    def _validate_semantic_model_elements(semantic_model: SemanticModel) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        element_info_tuples: List[Tuple[ElementReference, str, ValidationContext]] = []

        if semantic_model.measures:
            for measure in semantic_model.measures:
                element_info_tuples.append(
                    (
                        measure.reference,
                        "measure",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=measure.name
                            ),
                            element_type=SemanticModelElementType.MEASURE,
                        ),
                    )
                )
        if semantic_model.entities:
            for entity in semantic_model.entities:
                element_info_tuples.append(
                    (
                        entity.reference,
                        "entity",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=entity.name
                            ),
                            element_type=SemanticModelElementType.ENTITY,
                        ),
                    )
                )
        if semantic_model.dimensions:
            for dimension in semantic_model.dimensions:
                element_info_tuples.append(
                    (
                        dimension.reference,
                        "dimension",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=dimension.name
                            ),
                            element_type=SemanticModelElementType.DIMENSION,
                        ),
                    )
                )
        name_to_type: Dict[ElementReference, str] = {}

        for name, _type, context in element_info_tuples:
            if name in name_to_type:
                issues.append(
                    ValidationError(
                        context=context,
                        message=f"In semantic model `{semantic_model.name}`, can't use name `{name.element_name}` for "
                        f"a {_type} when it was already used for a {name_to_type[name]}",
                    )
                )
            else:
                name_to_type[name] = _type

        for name, _, context in element_info_tuples:
            issues += UniqueAndValidNameRule.check_valid_name(name=name.element_name, context=context)

        return issues

    @staticmethod
    @validate_safely(whats_being_done="checking model top level element names are sufficiently unique")
    def _validate_top_level_objects(model: SemanticManifest) -> List[ValidationIssue]:
        """Checks names of objects that are not nested."""
        object_info_tuples = []
        if model.semantic_models:
            for semantic_model in model.semantic_models:
                object_info_tuples.append(
                    (
                        semantic_model.name,
                        "semantic model",
                        SemanticModelContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model=SemanticModelReference(semantic_model_name=semantic_model.name),
                        ),
                    )
                )

        name_to_type: Dict[str, str] = {}

        issues: List[ValidationIssue] = []

        for name, type_, context in object_info_tuples:
            if name in name_to_type:
                issues.append(
                    ValidationError(
                        context=context,
                        message=f"Can't use name `{name}` for a {type_} when it was already used for a "
                        f"{name_to_type[name]}",
                    )
                )
            else:
                name_to_type[name] = type_

        if model.metrics:
            metric_names = set()
            for metric in model.metrics:
                if metric.name in metric_names:
                    issues.append(
                        ValidationError(
                            context=MetricContext(
                                file_context=FileContext.from_metadata(metadata=metric.metadata),
                                metric=MetricModelReference(metric_name=metric.name),
                            ),
                            message=f"Can't use name `{metric.name}` for a metric when it was already used for "
                            "a metric",
                        )
                    )
                else:
                    metric_names.add(metric.name)

        for name, _, context in object_info_tuples:
            issues += UniqueAndValidNameRule.check_valid_name(name=name, context=context)

        return issues

    @staticmethod
    @validate_safely(whats_being_done="running model validation ensuring elements have adequately unique names")
    def validate_model(model: SemanticManifest) -> Sequence[ValidationIssue]:  # noqa: D
        issues = []
        issues += UniqueAndValidNameRule._validate_top_level_objects(model=model)

        for semantic_model in model.semantic_models:
            issues += UniqueAndValidNameRule._validate_semantic_model_elements(semantic_model=semantic_model)

        return issues
