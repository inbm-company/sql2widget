import threading
import time
from types import SimpleNamespace

import pytest

from app import config, llm
from app import graph_extraction as ex
from app.graph_ingestion import GraphSourceError
from app.providers.openai import OpenAIProvider

SOURCE = {'id': 'src', 'tenant_id': 't', 'project_id': 'p'}
SCHEMA = {'entity_types': [{'name': 'Table', 'description': '', 'examples': ['a'], 'properties': []}],
          'relation_types': []}


def make_plan(count):
    return [{'id': f'src:{i}', 'path': 'a.md', 'heading': None, 'text': f'chunk {i}'} for i in range(count)]


class Recorder:
    """Stands in for the service DB repo and the Neo4j driver."""

    def __init__(self):
        self.progress, self.finished, self.merged = [], [], []

    def set_extract_progress(self, source_id, tenant_id, project_id, progress):
        self.progress.append(dict(progress))

    def finish_extract(self, *ids, **kwargs):
        self.finished.append(kwargs)


@pytest.fixture
def job(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(ex, 'repo', rec)
    monkeypatch.setattr(ex, 'graph_driver', lambda: SimpleNamespace(
        execute_query=lambda *a, **k: None,
        session=lambda **k: _Session()))
    monkeypatch.setattr(ex, 'write_entities', lambda *a: None)
    real_merge = ex.merge_results

    def merge(source_id, per_chunk):
        rec.merged = [chunk['id'] for chunk, _, _ in per_chunk]
        return real_merge(source_id, per_chunk)

    monkeypatch.setattr(ex, 'merge_results', merge)
    monkeypatch.setattr(config, 'EXTRACT_CONCURRENCY', 4)
    ex._cancel_events['src'] = threading.Event()
    yield rec
    ex._cancel_events.pop('src', None)


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute_write(self, *args):
        return None


def run(plan):
    ex.run_job(SOURCE, SCHEMA, plan, user_id='u', llm_settings={})


def test_chunks_run_in_parallel_up_to_the_limit_and_merge_in_chunk_order(job, monkeypatch):
    active, peak, lock = 0, 0, threading.Lock()

    def slow(chunk, schema, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.3 - 0.03 * int(chunk['id'].split(':')[1]))  # later chunks finish first
        with lock:
            active -= 1
        return [], []

    monkeypatch.setattr(ex, 'extract_chunk', slow)
    started = time.monotonic()
    run(make_plan(8))
    elapsed = time.monotonic() - started
    assert peak == 4
    assert elapsed < 1.2  # one worker would need about 1.6 s
    assert job.merged == [f'src:{i}' for i in range(8)]
    assert job.finished[-1]['status'] == 'completed'
    assert job.progress[-1] == {'done': 8, 'total': 8, 'failed': 0}


def test_scattered_failures_are_counted_and_do_not_stop_the_job(job, monkeypatch):
    def flaky(chunk, schema, **kwargs):
        if chunk['id'] in ('src:1', 'src:4'):
            raise GraphSourceError('bad answer')
        return [], []

    monkeypatch.setattr(config, 'EXTRACT_CONCURRENCY', 1)
    monkeypatch.setattr(ex, 'extract_chunk', flaky)
    run(make_plan(6))
    assert job.finished[-1]['status'] == 'completed'
    assert job.finished[-1]['progress'] == {'done': 6, 'total': 6, 'failed': 2}
    assert job.merged == ['src:0', 'src:2', 'src:3', 'src:5']


def test_three_failures_in_a_row_stop_the_job_and_skip_the_rest(job, monkeypatch):
    calls = []

    def always_fails(chunk, schema, **kwargs):
        calls.append(chunk['id'])
        time.sleep(0.05)  # a real call takes seconds; an instant failure would drain the queue first
        raise GraphSourceError('timed out')

    monkeypatch.setattr(config, 'EXTRACT_CONCURRENCY', 1)
    monkeypatch.setattr(ex, 'extract_chunk', always_fails)
    run(make_plan(20))
    assert job.finished[-1]['status'] == 'failed' and '연속 3개' in job.finished[-1]['error']
    assert len(calls) <= 5  # three failures plus calls already in flight; the queue was cancelled


def test_cancel_stops_waiting_without_publishing(job, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(ex, 'extract_chunk', lambda chunk, schema, **k: (release.wait(5), ([], []))[1])
    worker = threading.Thread(target=run, args=(make_plan(8),))
    worker.start()
    time.sleep(0.3)
    assert ex.request_cancel('src')
    worker.join(timeout=5)
    release.set()
    assert not worker.is_alive()
    assert job.finished[-1]['status'] == 'failed' and '취소' in job.finished[-1]['error']
    assert job.merged == []


def test_each_call_gets_the_extraction_timeout_and_the_retry_waits(monkeypatch):
    seen, naps = [], []
    answers = iter([{'result': None, 'error': 'timed out'}, {'result': {'entities': [], 'relations': []}}])

    def fake_llm(*args, **kwargs):
        seen.append(kwargs['timeout'])
        return next(answers)

    monkeypatch.setattr(ex, 'json_with_llm', fake_llm)
    monkeypatch.setattr(ex.time, 'sleep', naps.append)
    monkeypatch.setattr(config, 'EXTRACT_TIMEOUT_SECONDS', 180.0)
    assert ex.extract_chunk(make_plan(1)[0], SCHEMA, tenant_id='t', user_id='u', llm_settings={}) == ([], [])
    assert seen == [180.0, 180.0] and naps == [ex.RETRY_DELAY_SECONDS]


def test_timeout_reaches_the_http_call_only_when_given(monkeypatch):
    sent = []

    def post_json(*args, **kwargs):
        sent.append(kwargs)
        return {'choices': [{'message': {'content': '{"ok": true}'}}], 'usage': {}}

    monkeypatch.setattr('app.providers.transport.post_json', post_json)
    provider = OpenAIProvider(api_key='k')
    provider.plan('hint', {'q': 1})
    provider.plan('hint', {'q': 1}, timeout=180)
    assert 'timeout' not in sent[0] and sent[1]['timeout'] == 180


def test_json_with_llm_forwards_the_timeout(monkeypatch):
    calls = []

    class Adapter:
        name, model, api_key = 'openai', 'm', 'k'

        def plan(self, hint, content, **kwargs):
            calls.append(kwargs)
            return {'ok': True}, {}

    monkeypatch.setattr(llm, 'resolve_provider', lambda **k: Adapter())
    monkeypatch.setattr(llm, 'log_usage', lambda **k: None)
    common = {'tenant_id': 't', 'user_id': 'u', 'conversation_id': None}
    llm.json_with_llm('hint', {}, **common)
    llm.json_with_llm('hint', {}, timeout=180, **common)
    assert calls == [{}, {'timeout': 180}]
