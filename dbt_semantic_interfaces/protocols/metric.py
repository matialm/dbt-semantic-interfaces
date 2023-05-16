from __future__ import annotations

from abc import abstractmethod
from typing import List, Optional, Protocol

from dbt_semantic_interfaces.objects.filters.where_filter import WhereFilter
from dbt_semantic_interfaces.references import MeasureReference, MetricReference
from dbt_semantic_interfaces.type_enums.metric_type import MetricType
from dbt_semantic_interfaces.type_enums.time_granularity import TimeGranularity


class MetricInputMeasure(Protocol):
    """Provides a pointer to a measure along with metric-specific processing directives.

    If an alias is set, this will be used as the string name reference for this measure after the aggregation
    phase in the SQL plan.
    """

    name: str
    filter: Optional[WhereFilter]
    alias: Optional[str]

    @property
    @abstractmethod
    def measure_reference(self) -> MeasureReference:
        """Property accessor to get the MeasureReference associated with this metric input measure."""
        ...

    @property
    @abstractmethod
    def post_aggregation_measure_reference(self) -> MeasureReference:
        """Property accessor to get the MeasureReference with the aliased name, if appropriate."""
        ...


class _MetricInputMeasureMixin:
    """Mixin class to provide common functionality for MetricInputMeasure."""

    name: str
    alias: Optional[str]

    @property
    def measure_reference(self) -> MeasureReference:
        """Property accessor to get the MeasureReference associated with this metric input measure."""
        return MeasureReference(element_name=self.name)

    @property
    def post_aggregation_measure_reference(self) -> MeasureReference:
        """Property accessor to get the MeasureReference with the aliased name, if appropriate."""
        return MeasureReference(element_name=self.alias or self.name)


class MetricTimeWindow(Protocol):
    """Describes the window of time the metric should be accumulated over, e.g., '1 day', '2 weeks', etc."""

    count: int
    granularity: TimeGranularity


class MetricInput(Protocol):
    """Provides a pointer to a metric along with the additional properties used on that metric."""

    name: str
    filter: Optional[WhereFilter]
    alias: Optional[str]
    offset_window: Optional[MetricTimeWindow]
    offset_to_grain: Optional[TimeGranularity]

    @property
    @abstractmethod
    def as_reference(self) -> MetricReference:
        """Property accessor to get the MetricReference associated with this metric input."""
        ...


class _MetricInputMixin:
    """Mixin class to provide common functionality for MetricInput."""

    name: str

    @property
    def as_reference(self) -> MetricReference:
        """Property accessor to get the MetricReference associated with this metric input."""
        return MetricReference(element_name=self.name)


class MetricTypeParams(Protocol):
    """Type params add additional context to certain metric types (the context depends on the metric type)."""

    measure: Optional[MetricInputMeasure]
    measures: Optional[List[MetricInputMeasure]]
    numerator: Optional[MetricInputMeasure]
    denominator: Optional[MetricInputMeasure]
    expr: Optional[str]
    window: Optional[MetricTimeWindow]
    grain_to_date: Optional[TimeGranularity]
    metrics: Optional[List[MetricInput]]

    @property
    @abstractmethod
    def numerator_measure_reference(self) -> Optional[MeasureReference]:
        """Return the measure reference, if any, associated with the metric input measure defined as the numerator."""
        ...

    @property
    @abstractmethod
    def denominator_measure_reference(self) -> Optional[MeasureReference]:
        """Return the measure reference, if any, associated with the metric input measure defined as the denominator."""
        ...


class _MetricTypeParamsMixin:
    """Mixin class to provide common functionality for MetricTypeParams."""

    numerator: Optional[MetricInputMeasure]
    denominator: Optional[MetricInputMeasure]

    @property
    def numerator_measure_reference(self) -> Optional[MeasureReference]:
        """Return the measure reference, if any, associated with the metric input measure defined as the numerator."""
        return self.numerator.measure_reference if self.numerator else None

    @property
    def denominator_measure_reference(self) -> Optional[MeasureReference]:
        """Return the measure reference, if any, associated with the metric input measure defined as the denominator."""
        return self.denominator.measure_reference if self.denominator else None


class Metric(Protocol):
    """Describes a metric."""

    name: str
    description: Optional[str]
    type: MetricType
    type_params: MetricTypeParams
    filter: Optional[WhereFilter]

    @property
    @abstractmethod
    def input_measures(self) -> List[MetricInputMeasure]:
        """Return the complete list of input measure configurations for this metric."""
        ...

    @property
    @abstractmethod
    def measure_references(self) -> List[MeasureReference]:
        """Return the measure references associated with all input measure configurations for this metric."""
        ...

    @property
    @abstractmethod
    def input_metrics(self) -> List[MetricInput]:
        """Return the associated input metrics for this metric."""
        ...


class _MetricMixin:
    """Some useful default implementation details of MetricProtocol."""

    name: str
    type_params: MetricTypeParams

    @property
    def input_measures(self) -> List[MetricInputMeasure]:
        """Return the complete list of input measure configurations for this metric."""
        tp = self.type_params
        res = tp.measures or []
        if tp.measure:
            res.append(tp.measure)
        if tp.numerator:
            res.append(tp.numerator)
        if tp.denominator:
            res.append(tp.denominator)

        return res

    @property
    def measure_references(self) -> List[MeasureReference]:
        """Return the measure references associated with all input measure configurations for this metric."""
        return [x.measure_reference for x in self.input_measures]

    @property
    def input_metrics(self) -> List[MetricInput]:
        """Return the associated input metrics for this metric."""
        return self.type_params.metrics or []
