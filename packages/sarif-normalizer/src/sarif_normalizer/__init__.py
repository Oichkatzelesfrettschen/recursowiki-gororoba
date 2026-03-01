"""SARIF normalizer: conversion, merging, and deduplication for multi-tool SARIF output."""

from sarif_normalizer.merger import SarifMerger
from sarif_normalizer.deduplicator import SarifDeduplicator
from sarif_normalizer.severity_mapper import SeverityMapper

__all__ = ["SarifMerger", "SarifDeduplicator", "SeverityMapper"]
