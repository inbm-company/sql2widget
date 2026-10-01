"""Keep the user-visible processing record separate from raw diagnostic metadata."""

from copy import deepcopy


def message_meta(meta: dict) -> dict:
    # Never persist request headers, credentials, raw provider errors or SQL plans here.
    result = {key: deepcopy(meta[key]) for key in (
        "route", "route_source", "route_confidence", "route_candidate",
        "model", "retried", "graph_source_id", "graph_build",
    ) if key in meta}
    if meta.get("model"):
        result["provider"] = meta.get("provider")
    if meta.get("route_source") == "llm_fallback":
        result["route_fallback"] = True
    for section, keys in (
        ("knowledge", ("status", "entities_total", "entities_read", "relations_total", "relations_read", "truncated", "picked",
                       "entities_in_prompt", "relations_in_prompt", "prompt_entities", "used",
                       "used_entities", "used_relations")),
        ("schema_link", ("source", "reason", "total", "tables", "documented_tables",
                         "selected_descriptions", "escalated_to_full")),
    ):
        if section in meta:
            result[section] = {key: deepcopy(meta[section][key]) for key in keys if key in meta[section]}
    retrieval = meta.get("question_retrieval")
    if retrieval is not None:
        matches = retrieval.get("matches") or []
        result["question_retrieval"] = {
            "status": retrieval.get("status"), "count": len(matches),
            "references": [{"question": item.get("question"), "similarity": item.get("similarity")}
                           for item in matches],
        }
    return result
