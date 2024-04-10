import pandas as pd
from typing import Dict

from mindsdb.integrations.libs.api_handler import APIHandler
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
)
from mindsdb.utilities import log
from mindsdb_sql import parse_sql


_FINANCIAL_MODELING_URL = 'https://financialmodelingprep.com/api/v3/search?query=AA'

logger = log.getLogger(__name__)

class Financial_Modeling_Handler{
    def Financial_Modeling_Handler:
}