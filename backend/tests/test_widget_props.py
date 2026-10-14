import json
from contextlib import contextmanager
from decimal import Decimal

import pytest

from app import agent_service, config, question_similarity
from app.agent import sanitize_artifact
from app.contracts import QuestionIn
from app.repositories import stages
from app.widget_props import ANALYTICAL_COMPONENTS, analytical_rows_to_props


CASES = [
    ("StackedBarChart", [{"category": "서울", "series": "A", "value": Decimal("2.5")},
                         {"category": "부산", "series": "B", "value": -1},
                         {"category": "서울", "series": "A", "value": 1}],
     {"categories": ["서울", "부산"], "series": [{"name": "A", "data": [3.5, 0]}, {"name": "B", "data": [0, -1]}]}),
    ("Heatmap", [{"x": "서울", "y": "상품 A", "value": 0}, {"x": "서울", "y": "상품 A", "value": 2}],
     {"cells": [{"x": "서울", "y": "상품 A", "value": 2}]}),
    ("ScatterChart", [{"x": "1.25", "y": -2, "label": "A"}, {"x": 1.25, "y": -2}],
     {"points": [{"x": 1.25, "y": -2, "label": "A"}, {"x": 1.25, "y": -2}]}),
    ("Histogram", [{"bin_start": 10, "bin_end": 20, "count": 0},
                   {"bin_start": 0, "bin_end": 10, "count": 2},
                   {"bin_start": 0, "bin_end": 10, "count": 3}],
     {"bins": [{"start": 0, "end": 10, "count": 5}, {"start": 10, "end": 20, "count": 0}]}),
]






@pytest.mark.parametrize("component", sorted(ANALYTICAL_COMPONENTS))
def test_missing_aliases_raise_instead_of_guessing(component):
    with pytest.raises(ValueError, match="SQL requires columns"):
        analytical_rows_to_props(component, [{"unknown": 1}])


@pytest.mark.parametrize("value", ["bad", float("nan"), float("inf"), True])
def test_invalid_numeric_values_are_rejected(value):
    with pytest.raises(ValueError, match="finite number"):
        analytical_rows_to_props("ScatterChart", [{"x": value, "y": 1}])






