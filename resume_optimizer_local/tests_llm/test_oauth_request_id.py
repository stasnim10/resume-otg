"""Consent IDs are opaque Supabase identifiers, never UUID-only."""
import ast
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import pytest


def redirect_builder(state):
    source = Path(__file__).resolve().parents[1] / 'auth_state.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_with_pending_consent')
    namespace = dict(st=SimpleNamespace(session_state=state), urlencode=urlencode,
                     urlsplit=urlsplit, urlunsplit=urlunsplit)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_with_pending_consent']


def test_pending_opaque_consent_survives_google_redirect():
    identifier = '23nma3xzxbu7k62macdpommh7bokbpij'
    build = redirect_builder({'mcp_authorization_id': identifier})
    result = urlsplit(build('https://app.resumeotg.app/'))
    assert result.scheme == 'https'
    assert result.netloc == 'app.resumeotg.app'
    assert parse_qs(result.query) == {'authorization_id': [identifier]}
    assert not result.fragment


def test_normal_sign_in_has_no_consent_and_invalid_path_is_rejected():
    assert redirect_builder({})('https://app.resumeotg.app/') == 'https://app.resumeotg.app/'
    with pytest.raises(ValueError):
        redirect_builder({'mcp_authorization_id': '../consent?other=1'})('https://app.resumeotg.app/')
