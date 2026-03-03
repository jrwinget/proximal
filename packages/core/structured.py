"""Structured LLM output via tool_use / function calling."""

from __future__ import annotations

import json
import logging
from typing import TypeVar, Type

from pydantic import BaseModel, ValidationError

from .providers.router import chat

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def structured_output(
    prompt: str,
    response_model: Type[T],
    tool_name: str = "respond",
    tool_description: str = "Provide structured response",
    system_prompt: str | None = None,
) -> T:
    """Get structured output from an LLM using tool_use / function calling.

    Builds a tool definition from the pydantic model's JSON schema and
    forces the LLM to respond via that tool.  The tool call arguments are
    then validated back into a pydantic instance.

    Parameters
    ----------
    prompt : str
        The user prompt to send to the LLM.
    response_model : Type[T]
        A pydantic ``BaseModel`` subclass describing the desired output shape.
    tool_name : str, optional
        Name of the synthetic tool, by default ``"respond"``.
    tool_description : str, optional
        Description passed to the LLM for the tool, by default
        ``"Provide structured response"``.
    system_prompt : str or None, optional
        Optional system prompt prepended to the messages.

    Returns
    -------
    T
        A validated instance of *response_model*.

    Raises
    ------
    ValueError
        If the LLM does not return a tool call, the JSON cannot be parsed,
        or pydantic validation fails.
    """
    # build messages
    messages: list[dict] = []
    if system_prompt is not None:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # build tool definition from pydantic schema
    schema = response_model.model_json_schema()
    # remove pydantic metadata keys that confuse some providers
    schema.pop("title", None)
    schema.pop("$defs", None)

    tools = [
        {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": schema,
            },
        }
    ]

    # call the router — when tool_calls are present router returns the raw response
    response = await chat(
        messages=messages,
        tools=tools,
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )

    # extract tool call arguments
    # response may be a raw litellm ModelResponse when tool_calls are present
    if hasattr(response, "choices"):
        message = response.choices[0].message
    else:
        raise ValueError("No tool call returned by the model")

    if not hasattr(message, "tool_calls") or not message.tool_calls:
        raise ValueError("No tool call returned by the model")

    arguments_str = message.tool_calls[0].function.arguments

    # parse json
    try:
        data = json.loads(arguments_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in tool call arguments: {exc}") from exc

    # validate with pydantic
    try:
        return response_model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Validation failed for {response_model.__name__}: {exc}"
        ) from exc
