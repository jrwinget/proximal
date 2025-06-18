import weaviate

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
