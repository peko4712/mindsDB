import pandas as pd
from typing import Dict
from urllib.parse import urlencode
from mindsdb.integrations.libs.api_handler import APIHandler
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE
)
from mindsdb.integrations.handlers.financial_modeling_prep_handler.financial_modeling_tables import FinancialModelingTradesTable

from urllib.request import urlopen
from mindsdb.utilities import log
#from mindsdb_sql import parse_sql
import certifi
import json
import requests
# https://site.financialmodelingprep.com/developer/docs/daily-chart-charts
#To authorize your requests, add ?apikey= ----- at the end of every request.

_FINANCIAL_MODELING_URL = 'https://financialmodelingprep.com/api/v3/'

logger = log.getLogger(__name__)

class FinancialModelingHandler(APIHandler):
    def __init__(self, name, connection_data: dict,  **kwargs):
        super().__init__(name)

        self.api_key = None
        self.connection_data = connection_data
        #args = kwargs.get('connection_data', {})
        # if 'api_key' in args:
        #     self.api_key = args['api_key']
        
        self.api_key = connection_data['api_key']
        self.client = None
        self.is_connected = False

        daily_chart_table = FinancialModelingTradesTable(self) 
        self._register_table('daily_chart_table', daily_chart_table)

    def connect(self): 
        self.is_connected = True

    # def native_query(self, query: str = None) -> Response:
    #     ast = parse_sql(query, dialect='mindsdb')
    #     return self.query(ast)
    

    def get_daily_chart(self, params: Dict = None) -> pd.DataFrame:  
        base_url = "https://financialmodelingprep.com/api/v3/historical-price-full/"

        if 'symbol' not in params:
            raise ValueError('Missing "symbol" param')
        symbol = params['symbol']
        params.pop('symbol')

        limitParam = False

        if 'limit' in params:
            limit = params['limit']
            params.pop('limit')
            limitParam = True

        url = f"{base_url}{symbol}" #https://financialmodelingprep.com/api/v3/historical-price-full/<symbol>
        param = {'apikey': self.api_key, **params}

        response = requests.get(url, param)
        historical_data = response.json()
        historical = historical_data.get("historical")
        
        # if historical is not None:
        #     return pd.DataFrame(historical)
        # else:
        #     return pd.DataFrame() 

        # if limitParam:
        #     return {date: historical_data[date] for date in list(historical_data.keys())[:5]}
        # # air table handler 

        response = Response(
            RESPONSE_TYPE.TABLE,
            data_frame=pd.DataFrame(
                historical
            )
        )

        return pd.DataFrame(historical)
        #return response


    def call_financial_modeling_api(self, endpoint_name: str = None, params: Dict = None) -> pd.DataFrame:
        """Calls the financial modeling API method with the given params.

        Returns results as a pandas DataFrame.

        Args:
            
            params (Dict): Params to pass to the API call
        """
        print("Params:", params) 
        print(self.api_key)
        if endpoint_name == 'daily_chart':
            return self.get_daily_chart(params)
            #return None
        raise NotImplementedError('Endpoint {} not supported by Financial Modeling API Handler'.format(endpoint_name))
    