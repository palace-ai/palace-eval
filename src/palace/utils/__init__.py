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

"""Palace utilities."""

from palace.utils.io_adapters import IOAdapter, get_io_adapter, load_io_adapters
from palace.utils.model_extra_params import get_model_extra_params, load_model_extra_params
from palace.utils.multimodal import (
    build_multimodal_content,
    detect_modalities,
    is_image_attachment,
    mime_from_extension,
)

__all__ = [
    "is_image_attachment",
    "build_multimodal_content",
    "detect_modalities",
    "mime_from_extension",
    "IOAdapter",
    "load_io_adapters",
    "get_io_adapter",
    "load_model_extra_params",
    "get_model_extra_params",
]
