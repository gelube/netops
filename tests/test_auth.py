"""Tests for API token authentication middleware."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web'))


@pytest.fixture
def app():
    """Create test app with a known token."""
    os.environ['NETOPS_API_TOKEN'] = 'test-token-1234567890abcdef'
    # Must import after setting env var so the module picks it up
    # Clear any cached import
    for mod in list(sys.modules.keys()):
        if mod.startswith('app_local') or mod.startswith('blueprints'):
            del sys.modules[mod]
    from app_local import app as flask_app
    flask_app.config['TESTING'] = True
    yield flask_app
    del os.environ['NETOPS_API_TOKEN']


@pytest.fixture
def client(app):
    return app.test_client()


def test_local_request_no_token_ok(client):
    """Request from 127.0.0.1 should pass without token."""
    response = client.get('/api/sys/status', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    # Should not be 401 — could be 200 or another error, but NOT 401
    assert response.status_code != 401, "Local request should not require token"


def test_remote_request_no_token_401(client):
    """Request from non-local IP without token → 401."""
    response = client.get('/api/sys/status', environ_base={'REMOTE_ADDR': '10.0.0.1'})
    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert 'Unauthorized' in data['error']


def test_remote_request_valid_token(client):
    """Remote request with valid Bearer token → 200 (or non-401)."""
    response = client.get(
        '/api/sys/status',
        environ_base={'REMOTE_ADDR': '10.0.0.1'},
        headers={'Authorization': 'Bearer test-token-1234567890abcdef'}
    )
    assert response.status_code != 401, "Valid token should allow access"


def test_remote_request_invalid_token(client):
    """Remote request with wrong token → 401."""
    response = client.get(
        '/api/sys/status',
        environ_base={'REMOTE_ADDR': '10.0.0.1'},
        headers={'Authorization': 'Bearer wrong-token'}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False


def test_options_preflight_no_auth(client):
    """OPTIONS preflight requests should pass without auth"""
    os.environ['NETOPS_API_TOKEN'] = 'test-token-123'
    # Clear module cache if needed
    resp = client.open('/api/devices', method='OPTIONS',
                       environ_base={'REMOTE_ADDR': '10.0.0.1'})
    assert resp.status_code == 200


def test_exempt_routes_local(client):
    """Root route and static should be exempt from auth"""
    resp = client.get('/', environ_base={'REMOTE_ADDR': '10.0.0.1'})
    # Root route exempt even from remote
    assert resp.status_code != 401
