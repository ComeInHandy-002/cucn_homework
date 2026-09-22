from __future__ import annotations


def test_workstation_static_assets_and_bindings(client):
    page = client.get("/")
    styles = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    assert page.status_code == 200
    assert "工业安全智能监测系统" in page.text
    assert 'id="loginForm"' in page.text
    assert 'id="imageForm"' in page.text
    assert 'id="videoForm"' in page.text
    assert 'id="imageDemoAsset"' in page.text
    assert 'id="videoDemoAsset"' in page.text
    assert 'id="loadImageDemo"' in page.text
    assert 'id="loadVideoDemo"' in page.text
    assert 'id="zoneForm"' in page.text
    assert 'class="side-nav"' in page.text
    assert 'data-page-panel="overview"' in page.text
    assert 'data-page-panel="detection"' in page.text
    assert 'data-page-panel="jobs"' in page.text
    assert 'data-page-panel="experiments"' in page.text
    assert 'data-page-panel="alerts"' in page.text
    assert 'data-page-panel="configuration"' in page.text
    assert 'id="zoneCanvas"' in page.text
    assert 'id="eventsBody"' in page.text
    assert 'id="jobsBody"' in page.text
    assert 'id="jobResultModal"' in page.text
    assert 'id="jobResultPreview"' in page.text
    assert 'id="experimentModelsBody"' in page.text
    assert 'id="classMetricsTitle"' in page.text
    assert 'id="classMetricsSplitTag"' in page.text
    assert 'id="experimentTotalImages"' in page.text
    assert 'id="experimentTotalBoxes"' in page.text
    assert "Expanded PPE" in page.text
    assert styles.status_code == 200
    assert ".metric-grid" in styles.text
    assert ".sidebar" in styles.text
    assert ".donut" in styles.text
    assert ".job-summary-grid" in styles.text
    assert ".experiment-grid" in styles.text
    assert ".demo-picker" in styles.text
    assert "height: min(62vh, 560px)" in styles.text
    assert "position: absolute; inset: 0" in styles.text
    assert "max-height: 100%; object-fit: contain" in styles.text
    assert "height: min(62vh, 420px)" in styles.text
    assert script.status_code == 200
    assert "connectWebSocket" in script.text
    assert "drawZoneCanvas" in script.text
    assert "renderImageResult" in script.text
    assert "refreshJobs" in script.text
    assert "showJobResult" in script.text
    assert "/api/v1/jobs/${encodeURIComponent(jobId)}/result" in script.text
    assert "refreshExperiments" in script.text
    assert "refreshDemoAssets" in script.text
    assert "loadDemoAsset" in script.text
    assert "experimentTotalImages" in script.text
    assert "dataset_name" in script.text
    assert "model.is_current" in script.text
    for route in (
        "/health",
        "/api/v1/auth/login",
        "/api/v1/inference/images",
        "/api/v1/inference/videos",
        "/api/v1/jobs",
        "/api/v1/experiments/summary",
        "/api/v1/metrics/summary",
        "/api/v1/events",
        "/api/v1/cameras",
    ):
        assert route in script.text or route == "/health"
