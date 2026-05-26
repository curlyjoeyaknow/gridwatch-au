import pytest

from gridwatch.ports.datasource import DataSource
from gridwatch.ports.repository import Repository


def test_datasource_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DataSource()


def test_repository_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Repository()


def test_concrete_datasource_must_implement_fetch_readings():
    class Incomplete(DataSource):
        pass

    with pytest.raises(TypeError):
        Incomplete()

    class Complete(DataSource):
        def fetch_readings(self, region):
            return []

    assert Complete().fetch_readings("SA1") == []
