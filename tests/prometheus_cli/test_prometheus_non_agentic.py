"""Tests for the Prometheus-Prometheus-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"prometheus"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``prometheus-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "prometheus" tag namespace.

``is_prometheus_prometheus_non_agentic`` should only match the actual Prometheus
Prometheus-3 / Prometheus-4 chat family.
"""

from __future__ import annotations

import pytest

from prometheus_cli.model_switch import (
    _PROMETHEUS_MODEL_WARNING,
    _check_prometheus_model_warning,
    is_prometheus_prometheus_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "geohot0199/Prometheus-3-Llama-3.1-70B",
        "geohot0199/Prometheus-3-Llama-3.1-405B",
        "prometheus-3",
        "Prometheus-3",
        "prometheus-4",
        "prometheus-4-405b",
        "prometheus_4_70b",
        "openrouter/prometheus3:70b",
        "openrouter/geohot0199/prometheus-4-405b",
        "geohot0199/Prometheus3",
        "prometheus-3.1",
    ],
)
def test_matches_real_prometheus_prometheus_chat_models(model_name: str) -> None:
    assert is_prometheus_prometheus_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Prometheus Prometheus 3/4"
    )
    assert _check_prometheus_model_warning(model_name) == _PROMETHEUS_MODEL_WARNING


