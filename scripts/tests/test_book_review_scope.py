import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_book_review_scope import validate_review_scope
from verify_reader_review import validate_reader_review
from test_reader_review import package


def scope():
    return {'schema': 'book-review-scope-v1', 'book_facts': 'accept_as_source',
            'exceptions': [], 'items': [{'id': 'ch1', 'kind': 'source_fidelity'}]}


def test_default_scope_accepts_book_and_only_checks_fidelity():
    assert validate_review_scope(scope()) == []
    assert validate_review_scope({})
    assert validate_review_scope(None)
    data = scope()
    data['items'] = []
    assert validate_review_scope(data)


def test_external_fact_check_requires_specific_user_authorization():
    data = scope()
    data['items'] = [{'id': 'check-birth', 'kind': 'external_truth_check', 'exception_id': 'x'}]
    assert validate_review_scope(data)
    data['exceptions'] = [{'id': 'x', 'kind': 'external_truth_check', 'claim': '原书所记出生日期',
                           'source_location': '后记第1段', 'user_authorization': '用户明确要求仅核该日期'}]
    assert validate_review_scope(data) == []
    del data['exceptions'][0]['user_authorization']
    assert validate_review_scope(data)


def test_book_age_alone_does_not_authorize_research():
    data = scope()
    data['items'] = [{'id': 'update', 'kind': 'dated_update', 'exception_id': 'x'}]
    data['exceptions'] = [{'id': 'x', 'kind': 'dated_update', 'claim': '旧版操作方法',
                           'source_location': '第3章', 'book_age': 20}]
    assert validate_review_scope(data)
    data['exceptions'][0].update(change_reason='已找到现行官方指南明确改变此操作',
                                 current_source='https://example.org/current-guideline')
    assert validate_review_scope(data) == []


def test_style_cannot_block_delivery_or_trigger_another_review():
    data = scope()
    data['items'] = [{'id': 'word', 'kind': 'style', 'blocking': True}]
    assert validate_review_scope(data)
    data['items'][0]['blocking'] = False
    assert validate_review_scope(data) == []


def test_real_cli_rejects_empty_and_unapproved_truth_check(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'verify_book_review_scope.py'
    task = tmp_path / 'scope.json'
    for data in ({}, {**scope(), 'items': [{'id': 'all-book', 'kind': 'external_truth_check'}]}):
        task.write_text(json.dumps(data), encoding='utf-8')
        result = subprocess.run([sys.executable, str(script), str(task)], capture_output=True, text=True)
        assert result.returncode == 1
        assert '[review-scope]' in result.stdout
    task.write_text(json.dumps(scope()), encoding='utf-8')
    assert subprocess.run([sys.executable, str(script), str(task)], capture_output=True).returncode == 0


def test_reader_consumer_rejects_scope_mutation_even_when_hashes_match(tmp_path):
    distill, source, review, _, receipt = package(tmp_path)
    receipt.update(schema='reader-review-v2', review_scope=scope())
    review.write_text(json.dumps(receipt), encoding='utf-8')
    assert validate_reader_review(distill, source, review) == []
    original = copy.deepcopy(receipt)
    receipt['review_scope']['items'] = [{'id': 'all-book', 'kind': 'external_truth_check'}]
    review.write_text(json.dumps(receipt), encoding='utf-8')
    assert any('[review-scope]' in e for e in validate_reader_review(distill, source, review))
    del original['review_scope']
    review.write_text(json.dumps(original), encoding='utf-8')
    assert validate_reader_review(distill, source, review)
