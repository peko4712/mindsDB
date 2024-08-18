from mindsdb.integrations.libs.const import HANDLER_TYPE
from .__about__ import __version__ as version, __description__ as description
try:
    from .duckduckgozeroclick_handler import (
        DuckDuckGoHandler as Handler,
        connection_args_example,
        connection_args,
    )

    import_error = None
except Exception as e:
    Handler = None
    import_error = e

title = "DuckDuckGo"
name = "duckduckgozeroclick"
type = HANDLER_TYPE.DATA
icon_path = "icon.png"
description = "DuckDuckGo Zero-Click Info API integration"

__all__ = [
    "Handler", "name", "type", "title", "description",
    "import_error", "icon_path", "connection_args_example", "connection_args",
]