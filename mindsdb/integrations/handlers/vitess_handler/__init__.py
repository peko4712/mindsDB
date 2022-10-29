from mindsdb.integrations.libs.const import HANDLER_TYPE

try:
    from .vitess_handler import VitessHandler as Handler
    import_error = None
except Exception as e:
    Handler = None
    import_error = e
from .__about__ import __version__ as version, __description__ as description


title = 'Vitess'
name = 'vitess'
type = HANDLER_TYPE.DATA
icon_path = 'icon.png'

__all__ = [
    'Handler', 'version', 'name', 'type', 'title', 'description',
    'import_error', 'icon_path'
]
