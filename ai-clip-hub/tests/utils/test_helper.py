import json
import os
import pytest
from unittest.mock import patch

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from utils.helper import load_json

def test_load_json_success(tmp_path):
    # Arrange
    test_data = {"key": "value", "number": 42}
    test_file = tmp_path / "test.json"

    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)

    # Act
    result = load_json(str(test_file))

    # Assert
    assert result == test_data

def test_load_json_file_not_found():
    # Arrange
    non_existent_file = "does_not_exist.json"

    # Act
    result = load_json(non_existent_file)

    # Assert
    assert result is None

def test_load_json_invalid_json(tmp_path):
    # Arrange
    test_file = tmp_path / "invalid.json"

    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("{ invalid json format }")

    # Act
    result = load_json(str(test_file))

    # Assert
    assert result is None

@patch('utils.helper.logger')
def test_load_json_logs_error(mock_logger, tmp_path):
    # Arrange
    test_file = tmp_path / "invalid2.json"

    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("{ invalid json format }")

    # Act
    load_json(str(test_file))

    # Assert
    mock_logger.error.assert_called_once()
    args = mock_logger.error.call_args[0][0]
    assert "❌ Gagal memuat JSON" in args
