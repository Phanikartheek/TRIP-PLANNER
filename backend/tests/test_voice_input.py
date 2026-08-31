"""
Unit tests for Voice Input Speech-to-Text (/api/transcribe-audio).
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from trip_planner.api.app import app

client = TestClient(app)


def test_transcribe_audio_success():
    """
    Unit test: /api/transcribe-audio with mocked Groq Whisper API response.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "I want a relaxing beach holiday in South India with seafood."}

    audio_bytes = b"RIFF....WAVEfmt ....data...."

    with patch("requests.post", return_value=mock_resp) as mock_post:
        files = {"file": ("sample.wav", audio_bytes, "audio/wav")}
        response = client.post("/api/transcribe-audio", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "transcript" in data
        assert data["transcript"] == "I want a relaxing beach holiday in South India with seafood."
        mock_post.assert_called_once()


def test_reject_invalid_audio_file_types():
    """
    Unit test: Endpoint rejects invalid non-audio file types with 400 Bad Request.
    """
    text_bytes = b"Hello world, plain text document."
    resp = client.post(
        "/api/transcribe-audio",
        files={"file": ("notes.txt", text_bytes, "text/plain")}
    )
    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]
