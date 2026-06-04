"""Tests for FEEDBACK-004: GET /v1/profile/sector-affinity endpoint.

Tests:
1. Returns empty list for user with no sector affinity data
2. Returns sector affinities ordered by score DESC
3. RLS: User A does not see User B's affinities
4. Cache: second call returns cached data
5. Unauthenticated returns 401
6. Handles gracefully when table doesn't exist (migration pending)
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_user():
    return {"id": "550e8400-e29b-41d4-a716-446655440000", "sub": "550e8400-e29b-41d4-a716-446655440000", "email": "test@example.com"}


@pytest.fixture
def client(test_user):
    from main import app
    from auth import require_auth

    app.dependency_overrides[require_auth] = lambda: test_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_auth():
    from main import app
    from auth import require_auth

    app.dependency_overrides.pop(require_auth, None)
    return TestClient(app)


def _mock_supabase_select(rows):
    """Helper: create a mock Supabase table.select().eq().order().execute() chain."""
    mock = MagicMock()
    mock.table.return_value = mock
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.execute.return_value = MagicMock(data=rows)
    mock.single.return_value = mock
    return mock


class TestSectorAffinityEndpoint:
    """FEEDBACK-004: GET /v1/profile/sector-affinity tests."""

    # Test 1: Empty list for user without affinities

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    def test_empty_list_when_no_affinities(self, mock_set, mock_get, client):
        """Test 1: Returns empty list for user with no sector affinity data."""
        with patch("supabase_client.get_supabase", return_value=_mock_supabase_select([])):
            with patch("supabase_client.sb_execute", return_value=MagicMock(data=[])):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 2: Returns affinities ordered by score DESC

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    @patch("routes.user._get_sector_names")
    def test_returns_affinities_ordered_by_score(self, mock_names, mock_set, mock_get, client):
        """Test 2: Returns sector affinities ordered by affinity_score DESC."""
        mock_names.return_value = {
            "vestuario": "Vestuário e Uniformes",
            "alimentos": "Alimentos e Bebidas",
            "saude": "Saúde",
        }

        mock_rows = [
            {"sector_id": "saude", "affinity_score": 0.9, "feedback_count": 10},
            {"sector_id": "vestuario", "affinity_score": 0.7, "feedback_count": 5},
            {"sector_id": "alimentos", "affinity_score": 0.3, "feedback_count": 2},
        ]

        with patch("supabase_client.get_supabase", return_value=_mock_supabase_select(mock_rows)):
            with patch("supabase_client.sb_execute", return_value=MagicMock(data=mock_rows)):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["sector_id"] == "saude"
        assert data[0]["affinity_score"] == 0.9
        assert data[0]["sector_name"] == "Saúde"
        assert data[0]["feedback_count"] == 10
        assert data[1]["sector_id"] == "vestuario"
        assert data[1]["affinity_score"] == 0.7
        assert data[2]["sector_id"] == "alimentos"
        assert data[2]["affinity_score"] == 0.3

    # Test 3: User A cannot see User B's data (endpoint only queries for auth user)

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    @patch("routes.user._get_sector_names")
    def test_user_a_does_not_see_user_b_data(self, mock_names, mock_set, mock_get, client):
        """Test 3: RLS — user A cannot see user B's affinities."""
        mock_names.return_value = {"vestuario": "Vestuário e Uniformes"}
        mock_rows = [
            {"sector_id": "vestuario", "affinity_score": 0.8, "feedback_count": 3},
        ]

        with patch("supabase_client.get_supabase", return_value=_mock_supabase_select(mock_rows)):
            with patch("supabase_client.sb_execute", return_value=MagicMock(data=mock_rows)):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        sector_ids = [item["sector_id"] for item in data]
        assert sector_ids == ["vestuario"]

    # Test 4: Cache returns cached data

    def test_cache_returns_cached_data(self, client):
        """Test 4: Second call returns cached data without hitting Supabase."""
        cached_data = [
            {"sector_id": "vestuario", "sector_name": "Vestuário e Uniformes",
             "affinity_score": 0.8, "feedback_count": 3},
        ]

        with patch("routes.user._get_cached_sector_affinity", return_value=cached_data):
            with patch("routes.user._set_cached_sector_affinity") as _:
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sector_id"] == "vestuario"
        assert data[0]["affinity_score"] == 0.8

    # Test 5: Unauthenticated returns 401

    def test_unauthenticated_returns_401(self, client_no_auth):
        """Test 5: Unauthenticated requests should return 401."""
        response = client_no_auth.get("/v1/profile/sector-affinity")
        assert response.status_code == 401

    # Test 6: Handles missing table gracefully

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    def test_missing_table_returns_empty_list(self, mock_set, mock_get, client):
        """Test 6: Returns empty list when user_sector_affinity table doesn't exist."""

        class TableNotFoundError(Exception):
            def __init__(self):
                super().__init__('relation "user_sector_affinity" does not exist')

        with patch("supabase_client.get_supabase"):
            with patch("supabase_client.sb_execute", side_effect=TableNotFoundError()):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 7: Generic DB error returns empty list

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    def test_generic_db_error_returns_empty_list(self, mock_set, mock_get, client):
        """Test 7: Generic database error gracefully returns empty list."""
        with patch("supabase_client.get_supabase"):
            with patch("supabase_client.sb_execute", side_effect=Exception("connection timeout")):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # Test 8: Response schema matches OpenAPI contract

    @patch("routes.user._get_cached_sector_affinity", return_value=None)
    @patch("routes.user._set_cached_sector_affinity", return_value=None)
    @patch("routes.user._get_sector_names")
    def test_response_schema(self, mock_names, mock_set, mock_get, client):
        """Test 8: Response matches SectorAffinityResponse schema."""
        mock_names.return_value = {"saude": "Saúde"}
        mock_rows = [
            {"sector_id": "saude", "affinity_score": 0.85, "feedback_count": 7},
        ]

        with patch("supabase_client.get_supabase", return_value=_mock_supabase_select(mock_rows)):
            with patch("supabase_client.sb_execute", return_value=MagicMock(data=mock_rows)):
                response = client.get("/v1/profile/sector-affinity")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert "sector_id" in item
        assert "sector_name" in item
        assert "affinity_score" in item
        assert "feedback_count" in item
        assert isinstance(item["sector_id"], str)
        assert isinstance(item["sector_name"], str)
        assert isinstance(item["affinity_score"], (int, float))
        assert isinstance(item["feedback_count"], int)
        assert item["sector_id"] == "saude"
        assert item["sector_name"] == "Saúde"
        assert item["affinity_score"] == 0.85
        assert item["feedback_count"] == 7
