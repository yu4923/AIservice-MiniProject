from app.observability import graph_trace_config, request_id_context


def test_trace_config_links_request_without_profile_or_prompt():
    token = request_id_context.set("test-request-id")
    try:
        config = graph_trace_config(True)
        assert config["run_name"] == "youth_compass_chat"
        assert config["metadata"] == {"request_id": "test-request-id", "service": "fastapi"}
        assert config["recursion_limit"] == 16
    finally:
        request_id_context.reset(token)
    assert graph_trace_config(False)["run_name"] == "youth_compass_recommend"
