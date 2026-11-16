import pytest


@pytest.mark.integration
def test_conecta_a_neo4j(grafo_limpio):
    assert grafo_limpio.execute_query("RETURN 1 AS n").records[0]["n"] == 1
