import pytest

def test_get_auth_login(app_context):
    app, client = app_context
    rv = client.get('/auth/login')
    assert rv.status_code == 200
    assert b'Sign in to your account' in rv.data or b'AURA POS' in rv.data

def test_get_dashboard_redirects_anonymous(app_context):
    app, client = app_context
    # Ensure client is logged out, since client is session-scoped
    client.get('/auth/logout')
    rv = client.get('/dashboard')
    # Should redirect to auth.login
    assert rv.status_code == 302
    assert '/auth/login' in rv.location

def test_get_root_redirects(app_context):
    app, client = app_context
    rv = client.get('/')
    assert rv.status_code == 302 # redirect to dashboard, which redirects to login
    
def test_404_handler(app_context):
    app, client = app_context
    rv = client.get('/this-path-does-not-exist-123')
    assert rv.status_code == 404
    assert b'404' in rv.data
