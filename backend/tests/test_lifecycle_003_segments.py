"""Tests for LIFECYCLE-003 (#1428): User lifecycle segments endpoint.

Tests GET /admin/users/segments endpoint classification,
transition tracking, and power user detection.
Uses mocked Supabase client to avoid external API calls.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Valid UUID v4 test fixtures
VALID_UUID_1 = "550e8400-e29b-41d4-a716-446655440001"
VALID_UUID_2 = "550e8400-e29b-41d4-a716-446655440002"
VALID_UUID_3 = "550e8400-e29b-41d4-a716-446655440003"
ADMIN_UUID = "550e8400-e29b-41d4-a716-446655440000"


class TestUserLifecycleClassification:
    """Test suite for lifecycle classification logic."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create mock admin user with valid UUID."""
        return {
            "id": ADMIN_UUID,
            "email": "admin@example.com",
            "role": "authenticated",
        }

    @pytest.fixture
    def admin_app_with_overrides(self, mock_admin_user):
        """Create FastAPI app with admin router and auth override."""
        from fastapi import FastAPI
        from admin import router, require_admin

        app = FastAPI()
        app.include_router(router)

        async def mock_require_admin():
            return mock_admin_user

        app.dependency_overrides[require_admin] = mock_require_admin
        return app

    @pytest.fixture
    def client(self, admin_app_with_overrides):
        """Create test client with admin auth mocked."""
        return TestClient(admin_app_with_overrides)

    def test_segments_requires_admin(self):
        """Should return 401 without authentication."""
        from fastapi import FastAPI
        from admin import router

        app = FastAPI()
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/admin/users/segments")

        assert response.status_code == 401

    def test_segments_returns_state_counts(self, client):
        """Should return count_by_state with correct aggregation."""
        lifecycles = [
            {"user_id": VALID_UUID_1, "lifecycle": "trial_active"},
            {"user_id": VALID_UUID_2, "lifecycle": "trial_active"},
            {"user_id": VALID_UUID_3, "lifecycle": "paid_active"},
        ]

        mock_sb = Mock()

        # RPC mock
        rpc_result = Mock()
        rpc_result.data = lifecycles
        mock_rpc = Mock()
        mock_rpc.execute.return_value = rpc_result
        mock_sb.rpc.return_value = mock_rpc

        # Events mock
        events_table = Mock()
        events_result = Mock()
        events_result.data = []
        events_table.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = events_result
        mock_sb.table.return_value = events_table

        def table_side_effect(name):
            if name == "user_lifecycle_events":
                return events_table
            return Mock()

        mock_sb.table.side_effect = table_side_effect

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("admin._get_segments_cache", return_value=None):
            response = client.get("/admin/users/segments")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 3
        assert data["count_by_state"]["trial_active"] == 2
        assert data["count_by_state"]["paid_active"] == 1
        assert data["transitions_last_week"] == []
        assert data["power_users"] == []

    def test_segments_returns_cache_hit(self, client):
        """Should return cached data when available."""
        cached = {
            "count_by_state": {"trial_active": 5, "paid_active": 3},
            "total_users": 8,
            "transitions_last_week": [],
            "power_users": [],
            "queried_at": "2026-06-04T00:00:00+00:00",
        }

        with patch("admin._get_segments_cache", return_value=cached):
            response = client.get("/admin/users/segments")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 8
        assert data["count_by_state"]["trial_active"] == 5

    def test_segments_includes_power_users(self, client):
        """Should return power user details when power users exist."""
        lifecycles = [
            {"user_id": VALID_UUID_1, "lifecycle": "power_user"},
        ]

        sb = Mock()

        # RPC mock
        rpc_result = Mock()
        rpc_result.data = lifecycles
        mock_rpc = Mock()
        mock_rpc.execute.return_value = rpc_result
        sb.rpc.return_value = mock_rpc

        # Events mock
        events_table = Mock()
        events_result = Mock()
        events_result.data = []
        events_table.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = events_result

        # Profile mock for power user
        profile_result = Mock()
        profile_result.data = {
            "id": VALID_UUID_1,
            "email": "power@user.com",
            "full_name": "Power User",
            "company": "Power Corp",
        }
        profile_table = Mock()
        profile_table.select.return_value.eq.return_value.single.return_value.execute.return_value = profile_result

        # Count mocks for login_activity, pipeline_items, alerts
        count_result_14d = Mock()
        count_result_14d.count = 8
        count_mock_14d = Mock()
        count_mock_14d.select.return_value = count_mock_14d
        count_mock_14d.eq.return_value = count_mock_14d
        count_mock_14d.gte.return_value = count_mock_14d
        count_mock_14d.execute.return_value = count_result_14d

        count_result_pi = Mock()
        count_result_pi.count = 5
        count_mock_pi = Mock()
        count_mock_pi.select.return_value = count_mock_pi
        count_mock_pi.eq.return_value = count_mock_pi
        count_mock_pi.execute.return_value = count_result_pi

        count_result_al = Mock()
        count_result_al.count = 2
        count_mock_al = Mock()
        count_mock_al.select.return_value = count_mock_al
        count_mock_al.eq.return_value = count_mock_al
        count_mock_al.execute.return_value = count_result_al

        # Lifecycle cache mock
        lc_result = Mock()
        lc_result.data = {"lifecycle": "power_user"}
        lc_table = Mock()
        lc_table.select.return_value.eq.return_value.single.return_value.execute.return_value = lc_result

        # Side effects for table()
        def table_side_effect(name):
            if name == "user_lifecycle_events":
                return events_table
            elif name == "profiles":
                return profile_table
            elif name == "login_activity":
                return count_mock_14d
            elif name == "pipeline_items":
                return count_mock_pi
            elif name == "alerts":
                return count_mock_al
            elif name == "user_lifecycle":
                return lc_table
            return Mock()

        sb.table.side_effect = table_side_effect

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("admin._get_segments_cache", return_value=None), \
             patch("admin._set_segments_cache"):
            response = client.get("/admin/users/segments")

        assert response.status_code == 200
        data = response.json()
        assert len(data["power_users"]) == 1
        pu = data["power_users"][0]
        assert pu["user_id"] == VALID_UUID_1
        assert pu["email"] == "power@user.com"
        assert pu["full_name"] == "Power User"
        assert pu["logins_14d"] == 8
        assert pu["pipeline_count"] == 5
        assert pu["alert_count"] == 2

    def test_segments_includes_transitions(self, client):
        """Should return transitions from the last week."""
        lifecycles = [
            {"user_id": VALID_UUID_1, "lifecycle": "paid_active"},
        ]
        transitions = [
            {
                "user_id": VALID_UUID_1,
                "previous_lifecycle": "trial_active",
                "new_lifecycle": "paid_active",
                "changed_at": "2026-06-02T10:00:00+00:00",
            }
        ]

        sb = Mock()

        # RPC mock
        rpc_result = Mock()
        rpc_result.data = lifecycles
        mock_rpc = Mock()
        mock_rpc.execute.return_value = rpc_result
        sb.rpc.return_value = mock_rpc

        # Events mock
        events_table = Mock()
        events_result = Mock()
        events_result.data = transitions
        events_table.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = events_result

        def table_side_effect(name):
            if name == "user_lifecycle_events":
                return events_table
            return Mock()

        sb.table.side_effect = table_side_effect

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("admin._get_segments_cache", return_value=None), \
             patch("admin._set_segments_cache"):
            response = client.get("/admin/users/segments")

        assert response.status_code == 200
        data = response.json()
        assert len(data["transitions_last_week"]) == 1
        t = data["transitions_last_week"][0]
        assert t["user_id"] == VALID_UUID_1
        assert t["previous_lifecycle"] == "trial_active"
        assert t["new_lifecycle"] == "paid_active"

    def test_segments_handles_db_error_gracefully(self, client):
        """Should return 500 when Supabase call fails."""
        sb = Mock()
        sb.rpc.side_effect = Exception("DB connection error")

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("admin._get_segments_cache", return_value=None):
            response = client.get("/admin/users/segments")

        assert response.status_code == 500
        assert "segmentos" in response.json()["detail"].lower()

    def test_segments_empty_database(self, client):
        """Should handle empty database with no users."""
        sb = Mock()

        # RPC mock returns empty
        rpc_result = Mock()
        rpc_result.data = []
        mock_rpc = Mock()
        mock_rpc.execute.return_value = rpc_result
        sb.rpc.return_value = mock_rpc

        events_table = Mock()
        events_result = Mock()
        events_result.data = []
        events_table.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = events_result

        def table_side_effect(name):
            if name == "user_lifecycle_events":
                return events_table
            return Mock()

        sb.table.side_effect = table_side_effect

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("admin._get_segments_cache", return_value=None), \
             patch("admin._set_segments_cache"):
            response = client.get("/admin/users/segments")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 0
        assert data["count_by_state"] == {}
        assert data["transitions_last_week"] == []
        assert data["power_users"] == []


class TestSegmentsCache:
    """Test suite for segments caching."""

    @pytest.mark.asyncio
    async def test_cache_get_returns_none_when_empty(self):
        """Should return None when no cached data."""
        from admin import _get_segments_cache

        with patch("cache_module.redis_cache.get", return_value=None):
            result = await _get_segments_cache()

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_returns_parsed_json(self):
        """Should parse and return cached JSON data."""
        import json
        from admin import _get_segments_cache

        cached_data = {"total_users": 5, "count_by_state": {"trial_active": 3}}
        with patch("cache_module.redis_cache.get", return_value=json.dumps(cached_data)):
            result = await _get_segments_cache()

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_set_stores_data(self):
        """Should store serialized data in Redis."""
        import json
        from admin import _set_segments_cache

        mock_setex = Mock(return_value=True)
        with patch("cache_module.redis_cache.setex", mock_setex):
            data = {"total_users": 10, "count_by_state": {}}
            await _set_segments_cache(data)

        mock_setex.assert_called_once()
        args, kwargs = mock_setex.call_args
        assert args[0].startswith("smartlic:segments:")
        assert args[1] == 300  # 5 min TTL
        parsed = json.loads(args[2])
        assert parsed["total_users"] == 10

    @pytest.mark.asyncio
    async def test_cache_get_handles_redis_failure(self):
        """Should handle Redis failure gracefully."""
        from admin import _get_segments_cache

        with patch("cache_module.redis_cache.get", side_effect=Exception("Redis down")):
            result = await _get_segments_cache()

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_handles_redis_failure(self):
        """Should handle Redis failure gracefully on set."""
        from admin import _set_segments_cache

        with patch("cache_module.redis_cache.setex", side_effect=Exception("Redis down")):
            await _set_segments_cache({"total_users": 5})
