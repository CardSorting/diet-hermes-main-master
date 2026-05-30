# -*- coding: utf-8 -*-
"""RuntimeLayer boundary taxonomy tests."""
from __future__ import annotations


def test_representation_snapshot_maps_to_representation_layer():
    from plugins.dietcode.lib.agent.joyzoning.boundaries import RuntimeLayer, layer_for_event

    assert layer_for_event("representation.snapshot") is RuntimeLayer.REPRESENTATION
    assert layer_for_event("habitat.snapshot") is RuntimeLayer.REPRESENTATION
    assert RuntimeLayer.REPRESENTATION.value == "representation"


def test_habitat_enum_alias_points_at_representation():
    from plugins.dietcode.lib.agent.joyzoning.boundaries import RuntimeLayer

    assert RuntimeLayer.HABITAT is RuntimeLayer.REPRESENTATION


def test_representation_must_not_alias():
    from plugins.dietcode.lib.agent.joyzoning.boundaries import HABITAT_MUST_NOT, REPRESENTATION_MUST_NOT

    assert HABITAT_MUST_NOT is REPRESENTATION_MUST_NOT
