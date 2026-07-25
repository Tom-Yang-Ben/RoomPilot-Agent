from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
FLOOR04 = ROOT / "testdata" / "png" / "floor04.png"


pytestmark = pytest.mark.skipif(
    os.getenv("ROOMPILOT_BROWSER_E2E") != "1",
    reason="set ROOMPILOT_BROWSER_E2E=1 to run the browser CI gate",
)


def _browser_modules():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import WebDriverWait
    except ModuleNotFoundError as exc:
        pytest.fail(
            "ROOMPILOT_BROWSER_E2E=1 requires `uv sync --extra server --extra e2e`."
        )
    return webdriver, Options, By, Keys, WebDriverWait, ec


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str) -> None:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/scene/bootstrap", timeout=1)
            if response.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - diagnostic path.
            last_error = exc
        time.sleep(0.25)
    raise AssertionError(f"server did not start: {last_error!r}")


def _wait_for_room_axes(
    base_url: str,
    project_id: str,
    room_id: str,
    expected: dict[str, str],
) -> None:
    deadline = time.monotonic() + 20
    last_axes: dict[str, str] = {}
    while time.monotonic() < deadline:
        try:
            project = httpx.get(
                f"{base_url}/api/projects/{project_id}",
                timeout=3,
            ).json()["project"]
        except httpx.RequestError:
            time.sleep(0.2)
            continue
        axes = (
            project.get("workflow", {})
            .get("requirements", {})
            .get("rooms", {})
            .get(room_id, {})
            .get("axes", {})
        )
        last_axes = axes
        if all(axes.get(key) == value for key, value in expected.items()):
            return
        time.sleep(0.2)
    raise AssertionError(
        f"{room_id} technical answers were not persisted: "
        f"expected={expected}, actual={last_axes}"
    )


def _scheme_set(furniture: list[dict], design_preferences: dict) -> dict:
    return {
        "schemaVersion": "1.0",
        "activeSchemeId": "scheme-2",
        "generatedAt": "2026-07-24T00:00:00Z",
        "schemes": [
            {
                "id": "scheme-1",
                "title": "Scheme 1",
                "policy": "preserve",
                "status": "editable",
                "summary": "Preserve existing rooms.",
                "furniture": furniture[:1],
                "preferences": design_preferences,
                "generation": {
                    "source": "rule_fallback",
                    "ragStatus": "pending",
                    "agentStatus": "pending",
                    "placementEngine": "roompilot.engine",
                },
            },
            {
                "id": "scheme-2",
                "title": "Scheme 2",
                "policy": "balanced",
                "status": "editable",
                "summary": "Balanced scheme.",
                "furniture": furniture,
                "preferences": design_preferences,
                "generation": {
                    "source": "rule_fallback",
                    "ragStatus": "pending",
                    "agentStatus": "pending",
                    "placementEngine": "roompilot.engine",
                },
            },
            {
                "id": "scheme-3",
                "title": "Scheme 3",
                "policy": "functional",
                "status": "editable",
                "summary": "Functional scheme.",
                "furniture": furniture + [
                    {
                        "id": "living-storage",
                        "roomId": "living-room",
                        "type": "storage-cabinet",
                        "label": "Storage",
                        "widthCm": 160,
                        "depthCm": 45,
                        "xCm": 500,
                        "yCm": 150,
                    }
                ],
                "preferences": design_preferences,
                "generation": {
                    "source": "rule_fallback",
                    "ragStatus": "pending",
                    "agentStatus": "pending",
                    "placementEngine": "roompilot.engine",
                },
            },
        ],
    }


def _seed_floor04_project(base_url: str) -> str:
    project = httpx.post(
        f"{base_url}/api/projects",
        json={"name": "floor04 browser gate"},
        timeout=5,
    ).json()["project"]
    project_id = project["project_id"]
    with FLOOR04.open("rb") as file:
        upload = httpx.post(
            f"{base_url}/api/projects/{project_id}/floorplan",
            files={"file": (FLOOR04.name, file, "image/png")},
            timeout=10,
        )
    assert upload.status_code == 201

    rooms = [
        {
            "id": "living-room",
            "label": "Living Room",
            "type": "living_room",
            "polygon_cm": [
                {"x": 420, "y": 520},
                {"x": 820, "y": 520},
                {"x": 820, "y": 860},
                {"x": 420, "y": 860},
            ],
            "width_cm": 400,
            "depth_cm": 340,
        },
        {
            "id": "kitchen",
            "label": "Kitchen",
            "type": "kitchen",
            "polygon_cm": [
                {"x": 520, "y": 120},
                {"x": 820, "y": 120},
                {"x": 820, "y": 420},
                {"x": 520, "y": 420},
            ],
            "width_cm": 300,
            "depth_cm": 300,
        },
    ]
    design_preferences = {
        "schemaVersion": "1.0",
        "styleId": "scandinavian_1",
        "confirmed": False,
        "styleConfirmed": True,
        "materialsConfirmed": False,
        "wholeHouse": {
            "wallSurfaceId": "warm_white",
            "floorSurfaceId": "light_oak",
            "wallColor": "#f4efe4",
            "floorColor": "#c9a77d",
        },
        "rooms": {
            room["id"]: {
                "confirmed": False,
                "surfaceOverride": {},
                "materialPreferences": {},
            }
            for room in rooms
        },
        "notes": "browser gate",
    }
    furniture = [
        {
            "id": "living-sofa",
            "roomId": "living-room",
            "placement_room_id": "living-room",
            "type": "sofa",
            "label": "Sofa",
            "widthCm": 210,
            "depthCm": 90,
            "xCm": 560,
            "yCm": 690,
        }
    ]
    workflow = {
        "_flow": {
            "schemaVersion": 2,
            "projectId": project_id,
            "currentStep": "requirements",
            "completed": [
                "project",
                "upload",
                "recognition",
                "calibration",
                "space_confirmation",
            ],
            "data": {},
        },
        "privacy": {
            "accepted": True,
            "project_only": True,
            "no_training": True,
        },
        "recognition": {"source": "floor04-browser-e2e", "rooms": rooms},
        "calibration": {"distanceCm": 950},
        "confirmed_floorplan": {
            "floorplan": {
                "coordinate_unit": "cm",
                "width_cm": 950,
                "depth_cm": 950,
                "room_height_cm": 270,
            }
        },
        "space_confirmation": {
            "coordinate_unit": "cm",
            "rooms": rooms,
            "structures": {"walls": [], "doors": [], "windows": [], "columns": []},
        },
        "requirements": {
            "schemaVersion": "3.0",
            "mode": "designer_together",
            "basicConfirmed": True,
            "roomsResolved": True,
            "completed": True,
            "basic": {
                "residents": ["adult"],
                "residentCount": "two",
                "ageNeeds": ["none"],
                "scheduleInterference": ["same_schedule"],
                "homeWorkStudyCount": "none",
                "homeWorkStudyNeeds": ["none"],
                "futureChanges": ["stable"],
                "hostingFrequency": "rare",
                "hostingNeeds": ["none"],
                "budgetPriority": "balanced",
                "budgetRange": "undecided",
                "targetTimeline": "undecided",
                "immutableNeeds": ["none"],
            },
            "rooms": {
                "living-room": {
                    "schemaVersion": "3.0",
                    "confirmed": False,
                    "uses": ["\u65e5\u5e38\u4f11\u606f"],
                    "furniture": [],
                    "axes": {
                        "openness_storage": "balanced",
                        "social_focus": "balanced",
                        "seating_flexibility": "balanced",
                        "ceiling": "flat",
                        "air_conditioning": "wall_mounted",
                        "lighting": "layered_by_role",
                    },
                    "customNotes": {},
                    "stageNotes": {"uses": "", "furniture": ""},
                    "personalNeeds": "",
                },
                "kitchen": {
                    "schemaVersion": "3.0",
                    "confirmed": False,
                    "uses": ["\u6bcf\u65e5\u4e0b\u5eda"],
                    "furniture": [],
                    "axes": {
                        "kitchen_enclosure": "a",
                        "cooking_intensity": "balanced",
                        "worktop_storage": "balanced",
                    },
                    "customNotes": {},
                    "stageNotes": {"uses": "", "furniture": ""},
                    "personalNeeds": "",
                },
            },
            "keepExistingRoomIds": [],
            "settings": {"minimumFinishedHeightCm": 240},
        },
        "design_preferences": design_preferences,
    }
    saved = httpx.put(
        f"{base_url}/api/projects/{project_id}/workflow",
        json={"current_step": "requirements", "workflow": workflow},
        timeout=10,
    )
    assert saved.status_code == 200, saved.text
    return project_id


def test_floor04_step6_step7_browser_gate(tmp_path: Path) -> None:
    webdriver, Options, By, Keys, WebDriverWait, ec = _browser_modules()
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "ROOMPILOT_RUNTIME_DIR": str(tmp_path / "runtime"),
        "PYTHONPATH": str(ROOT),
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    driver = None
    try:
        _wait_for_server(base_url)
        project_id = _seed_floor04_project(base_url)

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1365,912")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
        driver.get(f"{base_url}/scene?project_id={project_id}")
        wait.until(ec.visibility_of_element_located((By.ID, "requirements-step")))

        def click_in_view(element) -> None:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'})",
                element,
            )
            wait.until(lambda _current: element.is_displayed() and element.is_enabled())
            element.click()

        def advance_to_technical_stage() -> None:
            for _ in range(3):
                click_in_view(driver.find_element(By.ID, "next-room-question"))
            wait.until(ec.visibility_of_element_located(
                (By.ID, "room-technical-preferences")
            ))

        def set_technical_values(values: dict[str, str]) -> None:
            for axis_id, value in values.items():
                option = driver.find_element(
                    By.CSS_SELECTOR,
                    f'[data-technical-axis="{axis_id}"] input[value="{value}"]',
                )
                driver.execute_script(
                    "arguments[0].click();",
                    option,
                )

        advance_to_technical_stage()
        living_technical = driver.find_elements(
            By.CSS_SELECTOR,
            "#room-technical-preference-options [data-technical-axis]",
        )
        assert [item.get_attribute("data-technical-axis") for item in living_technical] == [
            "ceiling",
            "air_conditioning",
            "lighting",
        ]
        technical_images = driver.find_elements(
            By.CSS_SELECTOR,
            "#room-technical-preference-options img.rp-axis-image",
        )
        assert len(driver.find_elements(
            By.CSS_SELECTOR,
            "#room-technical-preference-options input[type='radio']",
        )) == 6
        assert all(
            driver.execute_script("return arguments[0].complete", image)
            and driver.execute_script("return arguments[0].naturalWidth", image) > 0
            and driver.execute_script("return arguments[0].naturalHeight", image) > 0
            for image in technical_images
        )
        assert [
            item.find_element(By.CSS_SELECTOR, "input:checked").get_attribute("value")
            for item in living_technical
        ] == [
            "a",
            "a",
            "balanced",
        ]
        living_values = {
            "ceiling": "b",
            "air_conditioning": "b",
            "lighting": "a",
        }
        set_technical_values(living_values)
        click_in_view(driver.find_element(By.ID, "confirm-room-requirement"))
        wait.until(lambda current: "1 / 2" in current.find_element(
            By.ID, "requirements-progress"
        ).text)
        _wait_for_room_axes(
            base_url,
            project_id,
            "living-room",
            living_values,
        )

        driver.refresh()
        wait.until(ec.visibility_of_element_located((By.ID, "requirements-step")))
        advance_to_technical_stage()
        assert {
            item.get_attribute("data-technical-axis"): item.find_element(
                By.CSS_SELECTOR, "input:checked"
            ).get_attribute("value")
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                "#room-technical-preference-options [data-technical-axis]",
            )
        } == living_values

        click_in_view(driver.find_element(
            By.CSS_SELECTOR,
            '#room-question-nav [data-question-room="kitchen"]',
        ))
        advance_to_technical_stage()
        assert [
            item.get_attribute("data-technical-axis")
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                "#room-technical-preference-options [data-technical-axis]",
            )
        ] == ["ceiling", "lighting"]
        click_in_view(driver.find_element(By.ID, "confirm-room-requirement"))
        assert driver.find_element(By.ID, "requirements-error").text
        assert "1 / 2" in driver.find_element(By.ID, "requirements-progress").text

        kitchen_values = {"ceiling": "a", "lighting": "b"}
        set_technical_values(kitchen_values)
        click_in_view(driver.find_element(By.ID, "confirm-room-requirement"))
        wait.until(lambda current: "2 / 2" in current.find_element(
            By.ID, "requirements-progress"
        ).text)
        _wait_for_room_axes(base_url, project_id, "kitchen", kitchen_values)
        click_in_view(driver.find_element(By.ID, "confirm-requirements"))
        wait.until(ec.visibility_of_element_located((By.ID, "design-preferences-step")))
        assert not driver.find_elements(
            By.CSS_SELECTOR,
            "#design-preferences-step [data-technical-axis]",
        )

        assert len(driver.find_elements(By.CSS_SELECTOR, "[data-design-style-family]")) == 6
        assert len(driver.find_elements(By.CSS_SELECTOR, "[data-design-style]")) == 3
        assert len(driver.find_elements(By.CSS_SELECTOR, "#design-room-nav button")) == 2
        plan_image = driver.find_element(By.ID, "design-room-plan-image")
        assert plan_image.is_displayed()
        assert driver.execute_script("return arguments[0].naturalWidth", plan_image) > 0

        driver.set_window_size(390, 844)
        assert driver.execute_script(
            "return document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth"
        )
        assert len(
            driver.execute_script(
                "return getComputedStyle(document.querySelector('#design-style-grid'))"
                ".gridTemplateColumns.split(' ')"
            )
        ) == 1
        driver.set_window_size(1365, 912)

        style_variants = driver.find_elements(By.CSS_SELECTOR, "[data-design-style]")
        style_variants[0].click()
        driver.find_element(By.CSS_SELECTOR, '[data-design-material-tab="wall"]').click()
        card_selector = "#design-material-card-grid [data-design-surface-id]"
        wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, card_selector)) == 6)
        first_colorway_wall_ids = [
            card.get_attribute("data-design-surface-id")
            for card in driver.find_elements(By.CSS_SELECTOR, card_selector)
        ]
        assert driver.find_element(By.ID, "previous-design-material-page").get_attribute(
            "disabled"
        )
        assert not driver.find_element(By.ID, "next-design-material-page").get_attribute(
            "disabled"
        )
        assert "第 1 /" in driver.find_element(By.ID, "design-material-page-status").text

        style_variants = driver.find_elements(By.CSS_SELECTOR, "[data-design-style]")
        style_variants[2].click()
        wait.until(
            lambda current: [
                card.get_attribute("data-design-surface-id")
                for card in current.find_elements(By.CSS_SELECTOR, card_selector)
            ]
            != first_colorway_wall_ids
        )
        muted_colorway_wall_ids = [
            card.get_attribute("data-design-surface-id")
            for card in driver.find_elements(By.CSS_SELECTOR, card_selector)
        ]
        assert muted_colorway_wall_ids != first_colorway_wall_ids

        driver.find_element(By.ID, "next-design-material-page").click()
        wait.until(
            lambda current: "第 2 /"
            in current.find_element(By.ID, "design-material-page-status").text
        )
        second_page_ids = [
            card.get_attribute("data-design-surface-id")
            for card in driver.find_elements(By.CSS_SELECTOR, card_selector)
        ]
        assert len(second_page_ids) == 6
        assert set(second_page_ids).isdisjoint(muted_colorway_wall_ids)
        driver.find_element(By.ID, "previous-design-material-page").click()
        wait.until(
            lambda current: "第 1 /"
            in current.find_element(By.ID, "design-material-page-status").text
        )

        wall_tab = driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-tab="wall"]'
        )
        wall_tab.click()
        wall_tab.send_keys(Keys.ARROW_RIGHT)
        wait.until(
            lambda current: current.find_element(
                By.CSS_SELECTOR, '[data-design-material-tab="floor"]'
            ).get_attribute("aria-selected") == "true"
        )
        assert "第 1 /" in driver.find_element(
            By.ID, "design-material-page-status"
        ).text
        driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-tab="floor"]'
        ).send_keys(Keys.HOME)
        wait.until(lambda current: current.find_element(
            By.CSS_SELECTOR, '[data-design-material-tab="wall"]'
        ).get_attribute("aria-selected") == "true")

        click_in_view(driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-target="secondary"]'
        ))
        room_buttons = driver.find_elements(
            By.CSS_SELECTOR, "#design-room-nav [data-design-room]"
        )
        click_in_view(room_buttons[1])
        wait.until(lambda current: current.find_element(
            By.CSS_SELECTOR, '[data-design-material-target="primary"]'
        ).get_attribute("aria-pressed") == "true")
        click_in_view(driver.find_elements(
            By.CSS_SELECTOR, "#design-room-nav [data-design-room]"
        )[0])
        click_in_view(driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-target="secondary"]'
        ))
        material_cards = driver.find_elements(
            By.CSS_SELECTOR, "#design-material-card-grid [data-design-surface-id]"
        )
        click_in_view(material_cards[1])

        cut_editor = driver.find_element(By.ID, "design-cut-editor")
        driver.execute_script("arguments[0].open = true", cut_editor)
        wall_face = driver.find_element(By.ID, "design-cut-wall-face")
        driver.execute_script(
            "arguments[0].value = 'east';"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}))",
            wall_face,
        )
        canvas = driver.find_element(By.ID, "design-cut-canvas")
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'})",
            canvas,
        )
        canvas.send_keys(Keys.ENTER)
        canvas.send_keys(Keys.ARROW_UP)
        wait.until(lambda current: "右側牆" in current.find_element(
            By.ID, "design-cut-summary"
        ).text)

        click_in_view(driver.find_element(By.ID, "confirm-design-room"))
        wait.until(lambda current: current.find_element(
            By.ID, "design-room-progress"
        ).text == "1 / 2")

        click_in_view(driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-tab="wall"]'
        ))
        click_in_view(driver.find_elements(
            By.CSS_SELECTOR, "#design-material-card-grid [data-design-surface-id]"
        )[0])
        click_in_view(driver.find_element(
            By.CSS_SELECTOR, '[data-design-material-tab="floor"]'
        ))
        click_in_view(driver.find_elements(
            By.CSS_SELECTOR, "#design-material-card-grid [data-design-surface-id]"
        )[0])
        click_in_view(driver.find_element(By.ID, "confirm-design-room"))
        wait.until(lambda current: current.find_element(
            By.ID, "design-room-progress"
        ).text == "2 / 2")

        click_in_view(driver.find_element(By.ID, "confirm-design-preferences"))
        wait.until(ec.visibility_of_element_located((By.ID, "layout-2d-step")))
        assert len(driver.find_elements(
            By.CSS_SELECTOR, "#layout-scheme-tabs [data-layout-scheme]"
        )) == 3
        assert driver.find_element(By.ID, "workbench-glb-search").is_displayed()
        assert driver.find_element(By.ID, "workbench-wall-surface").is_displayed()
        assert driver.find_element(By.ID, "workbench-floor-surface").is_displayed()
        assert driver.find_element(By.ID, "workbench-cut-surface").is_displayed()
        assert driver.find_element(By.ID, "workbench-secondary-surface").is_displayed()
        _wait_for_room_axes(
            base_url,
            project_id,
            "living-room",
            living_values,
        )
        _wait_for_room_axes(
            base_url,
            project_id,
            "kitchen",
            kitchen_values,
        )
    finally:
        if driver is not None:
            driver.quit()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
