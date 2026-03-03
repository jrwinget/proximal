"""Voice capabilities — optional audio transcription and goal extraction."""

from __future__ import annotations

import re

from .registry import register_capability


@register_capability(
    name="transcribe_audio",
    description="Transcribe an audio file to text using whisper",
    category="voice",
    requires_llm=False,
)
def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file to text using OpenAI Whisper.

    Requires the ``[voice]`` optional extra which provides the ``whisper``
    package.

    Parameters
    ----------
    audio_path : str
        Path to the audio file to transcribe.

    Returns
    -------
    str
        The transcribed text.

    Raises
    ------
    ImportError
        If the ``whisper`` package is not installed.
    FileNotFoundError
        If the audio file does not exist.
    """
    try:
        import whisper  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "Voice features require the [voice] extra: pip install proximal[voice]"
        )

    import os

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]


@register_capability(
    name="extract_goals_from_transcript",
    description="Extract goal-like phrases from a text transcript",
    category="voice",
    requires_llm=False,
)
def extract_goals_from_transcript(transcript: str) -> list[str]:
    """Extract goal-like phrases from a transcript using pattern matching.

    Looks for common goal-indicating patterns such as "I want to ...",
    "I need to ...", "my goal is ...", etc. No LLM is needed for this
    basic extraction.

    Parameters
    ----------
    transcript : str
        The text transcript to extract goals from.

    Returns
    -------
    list[str]
        Extracted goal phrases, deduplicated and stripped.
    """
    if not transcript or not transcript.strip():
        return []

    # patterns that typically indicate goals or intentions
    patterns = [
        r"(?:I\s+)?(?:want|need|have)\s+to\s+(.+?)(?:\.|,|;|$)",
        r"(?:my|the)\s+goal\s+is\s+(?:to\s+)?(.+?)(?:\.|,|;|$)",
        r"I(?:'m| am)\s+(?:trying|planning|hoping)\s+to\s+(.+?)(?:\.|,|;|$)",
        r"(?:I\s+)?(?:should|must|ought\s+to)\s+(.+?)(?:\.|,|;|$)",
        r"(?:I\s+)?(?:would\s+like|wish)\s+to\s+(.+?)(?:\.|,|;|$)",
        r"let(?:'s| us)\s+(.+?)(?:\.|,|;|$)",
    ]

    goals: list[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        for match in matches:
            cleaned = match.strip()
            if cleaned and len(cleaned) > 3:
                goals.append(cleaned)

    # deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for goal in goals:
        lower = goal.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(goal)

    return unique
