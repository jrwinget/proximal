import os
import weaviate
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# skip Weaviate conn in test env
if os.getenv("SKIP_WEAVIATE_CONNECTION"):
    client = MagicMock()
    client.batch = MagicMock()
    client.batch.add_data_object = MagicMock()
else:
    client = weaviate.Client("http://localhost:8080")

    if not client.is_ready():
        raise RuntimeError("Cannot reach Weaviate at http://localhost:8080")

    schema = client.schema.get()
    classes = [c["class"] for c in schema.get("classes", [])]
    if "Memory" not in classes:
        client.schema.create_class(
            {
                "class": "Memory",
                "properties": [
                    {"name": "role", "dataType": ["text"]},
                    {"name": "content", "dataType": ["text"]},
                ],
                # think about passing "vectorIndexConfig" here
            }
        )


def store(role: str, content: str) -> None:
    """Helper to persist content with a role label."""
    client.batch.add_data_object({"role": role, "content": content}, "Memory")
