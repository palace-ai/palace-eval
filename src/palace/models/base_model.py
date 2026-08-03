# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

from abc import ABC, abstractmethod
from typing import Any

# Content can be plain text or multimodal parts (text + image_url dicts)
type MessageContent = str | list[dict[str, Any]]
type Message = dict[str, MessageContent]


class Model(ABC):
    """Base class for all language models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the model."""
        pass

    @abstractmethod
    def generate(self, messages: list[Message], **kwargs) -> str:
        """
        Generate a response given a conversation history.

        Args:
            messages: List of message dictionaries, each with `role` and `content` keys. `content` can be a string or a list of content parts (for multimodal). `role` can be either `system`, `user`, `assistant`, or `tool`. Optionally, there may be an additional `tool_name` key.
            **kwargs: Additional model-specific parameters

        Returns:
            The model's response as a string
        """
        pass
