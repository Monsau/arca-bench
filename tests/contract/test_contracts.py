"""Contract checks (pass 1): contract files exist and parse."""
import json
import os

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_openapi_yaml_parses():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(BASE, "contracts", "rest", "openapi.yaml"), encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert doc["openapi"].startswith("3.")


def test_graphql_schema_exists():
    with open(os.path.join(BASE, "contracts", "graphql", "schema.graphql"), encoding="utf-8") as f:
        assert "type Query" in f.read()


def test_mcp_capabilities_json_parses():
    with open(os.path.join(BASE, "contracts", "mcp", "capabilities.json"), encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["capabilities"], "at least one capability required"


def test_kafka_avro_schemas_parse():
    with open(os.path.join(BASE, "contracts", "kafka", "events.avsc"), encoding="utf-8") as f:
        doc = json.load(f)
    assert isinstance(doc, list) and doc, "expected a non-empty list of Avro schemas"
