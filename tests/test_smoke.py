import pytest
from app import create_app
from extensions import db

def test_app_creates_successfully():
    app = create_app('testing')
    assert app is not None
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'

def test_db_initializes(app_context):
    app, client = app_context
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        assert 'employees' in tables
        assert 'branches' in tables
        assert 'menu_items' in tables

def test_blueprints_registered():
    app = create_app('testing')
    blueprints = app.blueprints.keys()
    assert 'auth' in blueprints
    assert 'dashboard' in blueprints
    assert 'pos' in blueprints
