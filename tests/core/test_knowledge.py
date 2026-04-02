import os
import json
import pytest
from unittest.mock import patch, mock_open

from core.knowledge import KnowledgeBase

def test_extract_and_save_success(tmp_path):
    """Test successful extraction and saving to a temporary directory."""
    kb = KnowledgeBase(data_dir=str(tmp_path))
    topic = "Python Testing"
    video_data = {
        "transcript": "Ini adalah transkrip video tes.",
        "cta_used": "Subscribe sekarang!",
        "duration": 60
    }
    reward = 5.0

    result = kb.extract_and_save(topic, video_data, reward)

    assert result is True

    # Check if a file was created in the tmp_path
    files = list(tmp_path.glob("data_*.json"))
    assert len(files) == 1

    # Read the file and verify content
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["instruction"] == f"Buatkan naskah video pendek (Shorts/Reels) yang menarik tentang topik '{topic}'."
    assert data["input"] == f"Gunakan gaya bahasa ini dan tambahkan CTA '{video_data['cta_used']}'."
    assert data["output"] == video_data["transcript"]
    assert data["metadata"]["topic"] == topic
    assert data["metadata"]["simulated_reward"] == reward
    assert data["metadata"]["duration_seconds"] == video_data["duration"]
    assert "timestamp" in data["metadata"]

def test_extract_and_save_missing_transcript(tmp_path):
    """Test extraction failure when transcript is missing."""
    kb = KnowledgeBase(data_dir=str(tmp_path))
    topic = "Python Testing"
    video_data = {
        "cta_used": "Subscribe sekarang!",
        "duration": 60
    }

    result = kb.extract_and_save(topic, video_data)

    assert result is False
    assert len(list(tmp_path.glob("*.json"))) == 0

def test_extract_and_save_empty_video_data(tmp_path):
    """Test extraction failure when video_data is empty or None."""
    kb = KnowledgeBase(data_dir=str(tmp_path))

    # Test empty dict
    assert kb.extract_and_save("Topic", {}) is False
    assert len(list(tmp_path.glob("*.json"))) == 0

    # Test None
    assert kb.extract_and_save("Topic", None) is False
    assert len(list(tmp_path.glob("*.json"))) == 0

def test_extract_and_save_file_error(tmp_path):
    """Test extraction failure when file writing fails."""
    kb = KnowledgeBase(data_dir=str(tmp_path))
    topic = "Test"
    video_data = {"transcript": "Some text"}

    # Mock builtins.open to raise an exception
    with patch("builtins.open", mock_open()) as m:
        m.side_effect = IOError("Simulated disk full")
        result = kb.extract_and_save(topic, video_data)

    assert result is False
