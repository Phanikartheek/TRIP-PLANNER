"""
Unit tests for Photo-Based Destination Inspiration (/api/inspire-from-photo).
"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from trip_planner.api.app import app

client = TestClient(app)


def test_inspire_from_photo_success_and_eiffel_tower_mapping():
    """
    Unit test: /api/inspire-from-photo with mocked Groq vision response (Eiffel Tower scene).
    Confirms suggested_destinations and reasoning are parsed correctly and mapped to Indian destinations.
    """
    mock_vision_json = {
        "detected_scene": "The Eiffel Tower in Paris, France under a blue sky.",
        "suggested_destinations": ["Puducherry", "Jaipur", "Udaipur"],
        "reasoning": "While the photo shows the Eiffel Tower in Paris, per Phase 1 India-only scope, Puducherry offers French colonial architecture and European cafe culture, while Jaipur/Udaipur offer iconic romantic heritage landmarks."
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": f"```json\n{json.dumps(mock_vision_json)}\n```"
                }
            }
        ]
    }

    image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00"

    with patch("requests.post", return_value=mock_resp):
        files = {"file": ("eiffel.jpg", image_bytes, "image/jpeg")}
        response = client.post("/api/inspire-from-photo", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["detected_scene"] == "The Eiffel Tower in Paris, France under a blue sky."
        assert data["suggested_destinations"] == ["Puducherry", "Jaipur", "Udaipur"]
        assert "Puducherry" in data["suggested_destinations"]
        assert "Phase 1 India-only scope" in data["reasoning"] or "Puducherry" in data["reasoning"]


def test_reject_invalid_image_file_types():
    """
    Unit test: Endpoint rejects invalid non-image file types with 400 Bad Request.
    """
    text_bytes = b"Hello world, plain text document."
    resp = client.post(
        "/api/inspire-from-photo",
        files={"file": ("document.txt", text_bytes, "text/plain")}
    )
    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]
