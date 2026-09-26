"""Frontend serving contracts for both the Vue3 SPA and the legacy workbench."""

from __future__ import annotations

import re


def test_spa_shell_is_served_at_root(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "工业安全智能监测系统" in page.text
    assert '<div id="app">' in page.text
    assert "/assets/" in page.text


def test_spa_history_routes_fall_back_to_shell(client):
    for route in ("/overview", "/detection", "/jobs", "/experiments", "/alerts", "/configuration"):
        response = client.get(route)
        assert response.status_code == 200
        assert '<div id="app">' in response.text


def test_spa_assets_are_served(client):
    page = client.get("/")
    script_match = re.search(r'src="(/assets/[^"]+\.js)"', page.text)
    style_match = re.search(r'href="(/assets/[^"]+\.css)"', page.text)
    assert script_match and style_match
    assert client.get(script_match.group(1)).status_code == 200
    assert client.get(style_match.group(1)).status_code == 200


def test_legacy_workbench_remains_available(client):
    page = client.get("/static/index.html")
    styles = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    assert page.status_code == 200
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
    assert 'id="zoneCanvas"' in page.text
    assert 'id="eventsBody"' in page.text
    assert 'id="jobsBody"' in page.text
    assert 'id="jobResultModal"' in page.text
    assert 'id="experimentModelsBody"' in page.text
    assert "Expanded PPE" in page.text
    assert styles.status_code == 200
    assert ".metric-grid" in styles.text
    assert ".sidebar" in styles.text
    assert ".donut" in styles.text
    assert ".job-summary-grid" in styles.text
    assert ".experiment-grid" in styles.text
    assert "height: min(62vh, 560px)" in styles.text
    assert "position: absolute; inset: 0" in styles.text
    assert "max-height: 100%; object-fit: contain" in styles.text
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
