"""Tests for voice capabilities — transcription and goal extraction."""

import pytest
from unittest.mock import patch, MagicMock

from packages.core.capabilities.voice import (
    extract_goals_from_transcript,
    transcribe_audio,
)


class TestTranscribeAudio:
    def test_transcribe_calls_whisper(self, tmp_path):
        """transcribe_audio should load a whisper model and call transcribe."""
        # create a dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "I want to build an app"}

        mock_whisper = MagicMock()
        mock_whisper.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            result = transcribe_audio(str(audio_file))

        assert result == "I want to build an app"
        mock_whisper.load_model.assert_called_once_with("base")
        mock_model.transcribe.assert_called_once_with(str(audio_file))

    def test_transcribe_raises_import_error(self):
        """transcribe_audio should raise ImportError when whisper is missing."""
        with patch.dict("sys.modules", {"whisper": None}):
            with pytest.raises(ImportError, match="Voice features require"):
                transcribe_audio("nonexistent.wav")

    def test_transcribe_raises_file_not_found(self, tmp_path):
        """transcribe_audio should raise FileNotFoundError for missing files."""
        mock_whisper = MagicMock()

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            with pytest.raises(FileNotFoundError, match="Audio file not found"):
                transcribe_audio(str(tmp_path / "missing.wav"))


class TestExtractGoals:
    def test_extract_want_to(self):
        """Should extract 'I want to ...' patterns."""
        transcript = "I want to learn Python. Also I want to build an app."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) == 2
        assert "learn Python" in goals
        assert "build an app" in goals

    def test_extract_need_to(self):
        """Should extract 'I need to ...' patterns."""
        transcript = "I need to finish the report by Friday."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) >= 1
        assert any("finish the report" in g for g in goals)

    def test_extract_goal_is(self):
        """Should extract 'my goal is ...' patterns."""
        transcript = "My goal is to run a marathon this year."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) >= 1
        assert any("run a marathon" in g for g in goals)

    def test_extract_planning_to(self):
        """Should extract 'I'm planning to ...' patterns."""
        transcript = "I'm planning to renovate the kitchen."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) >= 1
        assert any("renovate the kitchen" in g for g in goals)

    def test_extract_should(self):
        """Should extract 'I should ...' patterns."""
        transcript = "I should exercise more regularly."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) >= 1
        assert any("exercise more regularly" in g for g in goals)

    def test_extract_deduplicates(self):
        """Should deduplicate identical goals."""
        transcript = "I want to learn Python. I want to learn Python."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) == 1

    def test_extract_empty_transcript(self):
        """Should return empty list for empty input."""
        assert extract_goals_from_transcript("") == []
        assert extract_goals_from_transcript("   ") == []

    def test_extract_no_goals(self):
        """Should return empty list when no goal patterns are found."""
        transcript = "The weather is nice today."
        goals = extract_goals_from_transcript(transcript)
        assert goals == []

    def test_extract_lets(self):
        """Should extract 'let's ...' patterns."""
        transcript = "Let's organize the office this weekend."
        goals = extract_goals_from_transcript(transcript)
        assert len(goals) >= 1
        assert any("organize the office" in g for g in goals)
