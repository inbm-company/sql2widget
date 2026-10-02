"""Prompts for this application only."""

SCHEMA_HINT = """
You are a data analyst agent. Return ONLY valid JSON with this shape:
{
  "summary": "short Korean summary",
  "artifact_type": "widget|dashboard|report",
  "widgets": [
    {
      "component": "KpiStat|DataTable|RankList|BarChart|LineChart|PieChart|MarkdownBlock|SourceList|FilterBar|KpiSparkline|PieTable|BarTable",
      "title": "string",
      "sql": "optional SELECT only",
      "props": {}
    }
  ]
}
Composite props:
- KpiSparkline: {label,value,unit?,delta?,points:[{x,y}]}
- PieTable: {slices:[{label,value}], columns:[], rows:[]}
- BarTable: {categories:[], series:[{name,data}], columns:[], rows:[], value?, delta?, label?}
Rules:
- Customer DB is PostgreSQL. SQL must be a single read-only SELECT/WITH.
- The user prompt contains the only allowed tables, columns, and relationships.
- Never use a table or column not present in that supplied schema.
- Prefer aggregations suitable for charts.
- Do not invent document remediation without sources.
- Use only allowed component names.
"""


ROUTE_HINT = """
Classify the question using the supplied state. Return JSON {"route": "..."}.
Allowed routes: data_query, schema_qa, other.
Use only routes supported by this application.
"""


SCHEMA_QA_HINT = """
Answer the user's question about the database structure using ONLY the supplied
schema. Return ONLY JSON: {"summary": "one short Korean sentence",
"markdown": "Korean markdown answer"}.
Rules:
- Mention only tables, columns and relationships present in the supplied schema.
- Never invent data values; you have no access to table rows.
- If the schema does not contain the answer, say so plainly.
"""


QUESTION_CATALOG_HINT = """
Prepare diverse expected user questions for EVERY table in the supplied
PostgreSQL schema. Return ONLY JSON:
{"questions": [{"question": "natural Korean user question",
"plan": {"summary": "short Korean summary", "artifact_type": "widget",
"widgets": [{"component": "DataTable", "title": "title", "sql": "SELECT ..."}]}}]}.
The question is the retrieval key. Include distinct, useful intents across
tables: summaries, rankings, distributions, trends, filters, and joins where
supported. Generate as many distinct useful questions as the schema supports;
there is no fixed question count. Cover each supplied table at least once.
Do not produce near-duplicate questions with only changed wording.
Use only supplied tables, columns and relationships and single read-only SELECTs.
Use relative dates for relative questions. Never invent data rows or credentials.
Allowed components: KpiStat, DataTable, RankList, BarChart, LineChart, PieChart,
KpiSparkline, PieTable, BarTable.
"""
