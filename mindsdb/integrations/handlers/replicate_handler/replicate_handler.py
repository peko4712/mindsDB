import replicate
import pandas as pd
from mindsdb.integrations.libs.base import BaseMLEngine
from typing import Dict, Optional
import os
import types
from mindsdb.utilities.config import Config


class ReplicateHandler(BaseMLEngine):
    name = "replicate"

    @staticmethod
    def create_validation(target, args=None, **kwargs):
        if 'using' not in args:
            raise Exception("Replicate engine requires a USING clause! Refer to its documentation for more details.")
        else:
            args = args['using']

        if 'model_name' and 'version' not in args:
            raise Exception('Add model_name and version ')

            # Checking if passed model_name and version  are correct or not
        try:
            replicate.default_client.api_token = args['api_key']
            replicate.models.get(args['model_name']).versions.get(args['version'])
        except Exception as e:
            raise Exception("Check your model_name and version carefully", e)

    def create(self, target: str, df: Optional[pd.DataFrame] = None, args: Optional[Dict] = None) -> None:
        """Saves model details in stirage to access it later
        """
        args = args['using']
        args['target'] = target
        self.model_storage.json_set('args', args)

    def predict(self, df: pd.DataFrame, args: Optional[Dict] = None) -> pd.DataFrame:
        """Using replicate makes the prediction according to your parameters
        """
        def filter_images(x):
            output = replicate.run(
                    f"{args['model_name']}:{args['version']}",
                    input={**x[1].to_dict(), **pred_args}) # unpacking parameters inputted

            if isinstance(output, types.GeneratorType):
                # getting final url if output is generator of frames url
                output = [list(output)[-1]]
                return output
            else:
                return output

        pred_args = args['predict_params'] if args else {}
        args = self.model_storage.json_get('args')
        
        # raiseing Exception if wrong parameters is given
        params_names = set(df.columns) | set(pred_args)
        available_params = self._get_schema(only_keys=True)
        wrong_params = []
        for i in params_names:
            if i not in available_params:
                wrong_params.append(i)

        if wrong_params:
            raise Exception(f"""
'{wrong_params}' is/are not supported parameter for this model.
Use DESCRIBE PREDICTOR mindsdb.<model_name>.features; to know about available parameters. OR 
Visit https://replicate.com/f{args['model_name']}/versions/{args['version']} to check parameters.
            """)

        replicate.default_client.api_token = self._get_replicate_api_key(args)

        rows = df.iterrows()      # Generator is returned
        rows_arr = list(rows)      # Generator converted to list have tuple consisting (index, row(pandas.Series))

        urls = map(filter_images, rows_arr)  # using filter_images function to get url according to inputted parameters
        urls = pd.DataFrame(urls)
        urls.columns = [args['target']]
        return urls

    def create_engine(self, connection_args: dict):
        #  Implement such that with this api key can be set
        pass

    def describe(self, attribute: Optional[str] = None) -> pd.DataFrame:

        if attribute == "features":
            return self._get_schema()

        else:
            return pd.DataFrame(['features'],columns=['tables'])

    def _get_replicate_api_key(self, args, strict=True):
        """ 
        API_KEY preference order:
            1. provided at model creation
            2. provided at engine creation
            3. REPLICATE_API_KEY env variable
            4. replicate.api_key setting in config.json
        """  # noqa
        # 1
        if 'api_key' in args:
            return args['api_key']
        # 2
        connection_args = self.engine_storage.get_connection_args()
        if 'api_key' in connection_args:
            return connection_args['api_key']
        # 3
        api_key = os.getenv('REPLICATE_API_TOKEN')
        if api_key is not None:
            return api_key
        # 4
        config = Config()
        replicate_cfg = config.get('replicate', {})
        if 'api_key' in replicate_cfg:
            return replicate_cfg['api_key']

        if strict:
            raise Exception(f'Missing API key "api_key". Either re-create this ML_ENGINE specifying the `api_key` parameter,\
                 or re-create this model and pass the API key with `USING` syntax.')

    def _get_schema(self, only_keys=False):
        '''Return paramters list with it description,default and type,
         which helps user to customize there prediction '''

        args = self.model_storage.json_get('args')
        os.environ['REPLICATE_API_TOKEN'] = self._get_replicate_api_key(args)
        replicate.default_client.api_token = self._get_replicate_api_key(args)
        model = replicate.models.get(args['model_name'])
        version = model.versions.get(args['version'])
        schema = version.get_transformed_schema()['components']['schemas']['Input']['properties']

        # returns only list of paramater 
        if only_keys:
            return schema.keys()

        for i in list(schema.keys()):
            for j in list(schema[i].keys()):
                if j not in ['default', 'description', 'type']:
                    schema[i].pop(j)

        df = pd.DataFrame(schema).T
        df = df.reset_index().rename(columns={'index': 'inputs'})
        return df.fillna('-')
