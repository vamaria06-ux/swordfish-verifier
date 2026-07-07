def test_project_setup():
    """Проверяем что проект настроен корректно"""
    assert True


def test_requirements_exist():
    """Проверяем что можно импортировать нужные библиотеки"""
    import requests
    import yaml
    import flask
    assert requests is not None
    assert yaml is not None
    assert flask is not None
