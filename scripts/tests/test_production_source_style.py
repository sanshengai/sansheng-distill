import json
import sys
from pathlib import Path
import pytest
from test_reader_review import production_package
import verify_page
from verify_reader_review import sha256


def styled_package(tmp_path):
    distill, source, review, data, receipt = production_package(tmp_path)
    sentence = '父母和孩子需要在家庭共同生活的情境中理解彼此的需要并且尊重每个人拥有的权利和承担的责任。'
    data['chapters'][0].update(title='鼓励', narrative=sentence+sentence)
    distill.write_text(json.dumps(data, ensure_ascii=False))
    receipt['distill_sha256'] = sha256(distill.read_bytes())
    receipt['chapters'][0]['narrative_sha256'] = sha256(data['chapters'][0]['narrative'].encode())
    review.write_text(json.dumps(receipt))
    return distill, source, review, data, receipt


def test_explicit_production_style_preserves_titles_and_repetition(tmp_path):
    distill, source, review, data, _ = styled_package(tmp_path)
    production = verify_page.verified_production_style(distill, source, review)
    assert production
    legacy = verify_page.lint_distill(data, source.read_text())
    assert any('标题非论点式' in x for x in legacy)
    assert any('重复句' in x for x in legacy)
    errors = verify_page.lint_distill(data, source.read_text(), production_only=production)
    assert not any('标题非论点式' in x or '重复句' in x for x in errors)
    data['chapters'][0]['narrative'] = ''
    assert any('正文为空' in x for x in verify_page.lint_distill(data, source.read_text(), production_only=True))


@pytest.mark.parametrize('mutation', ['missing_receipt', 'no_user_instruction', 'fake_review', 'stale_hash', 'empty_source', 'empty_body', 'missing_unit'])
def test_production_style_rejects_invalid_authorization_and_assembly(tmp_path, mutation):
    distill, source, review, data, receipt = styled_package(tmp_path)
    if mutation == 'missing_receipt':
        review.unlink()
    elif mutation == 'no_user_instruction':
        receipt.pop('user_no_content_review')
    elif mutation == 'fake_review':
        receipt['chapters'][0]['fidelity'] = 'reviewed'
    elif mutation == 'stale_hash':
        distill.write_text(distill.read_text()+'\n')
    elif mutation == 'empty_source':
        source.write_text('')
        receipt['source_sha256'] = sha256(source.read_bytes())
    elif mutation == 'empty_body':
        data['chapters'][0]['narrative'] = ''
        distill.write_text(json.dumps(data))
        receipt['distill_sha256'] = sha256(distill.read_bytes())
        receipt['chapters'][0]['narrative_sha256'] = sha256(b'')
    elif mutation == 'missing_unit':
        receipt['chapters'] = []
    if mutation != 'missing_receipt':
        review.write_text(json.dumps(receipt))
    assert not verify_page.verified_production_style(distill, source, review)


def test_actual_cli_rejects_style_without_valid_production_receipt(tmp_path, monkeypatch):
    distill, source, review, data, receipt = styled_package(tmp_path)
    page = tmp_path/'page.html';page.write_text('<html></html>')
    original = verify_page.lint_distill
    def isolated_html(html, distill, enrich, **kwargs):
        return [x for x in original(distill, production_only=kwargs.get('production_only', False)) if '标题非论点式' in x]
    monkeypatch.setattr(verify_page, 'lint_html', isolated_html)
    monkeypatch.setattr(sys, 'argv', ['verify_page', str(page), '--distill', str(distill), '--source', str(source), '--reader-review', str(review), '--skip-interact'])
    assert verify_page.main() == 0
    receipt.pop('user_no_content_review');review.write_text(json.dumps(receipt))
    assert verify_page.main() == 1
