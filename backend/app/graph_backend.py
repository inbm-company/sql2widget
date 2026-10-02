"""Optional graph connection/read foundation. Not called by SQL chat or exposed in the UI."""
import os
from functools import lru_cache
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

class GraphError(ValueError):
    pass

@lru_cache(maxsize=1)
def graph_driver():
    if os.getenv("GRAPH_ENABLED", "false").lower() != "true":
        raise GraphError("그래프 기능은 현재 사용하지 않습니다.")
    password = os.getenv("NEO4J_PASSWORD", "")
    uri = os.getenv("NEO4J_URI", "")
    if not password or not uri:
        raise GraphError("그래프 연결 설정이 없습니다.")
    return GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USERNAME", "neo4j"), password),
                               connection_timeout=10, max_transaction_retry_time=15)

def read_graph(reader, *args):
    """Execute a trusted, application-defined read callback (no arbitrary SQL-chat queries)."""
    try:
        with graph_driver().session(database="neo4j") as session:
            return session.execute_read(reader, *args)
    except (DriverError, Neo4jError, OSError) as exc:
        raise GraphError("그래프를 조회하지 못했습니다.") from exc

def close_graph_driver():
    if graph_driver.cache_info().currsize:
        graph_driver().close()
        graph_driver.cache_clear()
