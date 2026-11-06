import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        # API suite + any test loading the seeded client exercise official files.
        marker='official' if item.path.name=='test_api.py' or 'client' in item.fixturenames else 'synthetic'
        item.add_marker(getattr(pytest.mark,marker))
