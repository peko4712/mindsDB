from typing import Optional, Dict
import pandas as pd
import transformers
import requests

from monkeylearn import MonkeyLearn

from mindsdb.integrations.libs.base import BaseMLEngine


class monkeylearnHandler(BaseMLEngine):
    name = "MonkeyLearn"

    def create(self, target: str, df: Optional[pd.DataFrame] = None, args: Optional[Dict] = None) -> None:
        args = args['using']
        model_id = args['MODEL_ID']
        API_key = args['YOUR_API_KEY']
        # if 'production_model' in args:
        #     raise Exception("Custom models are not supported currently")

        # Check whether the model_id given by user exists in the user account or monkeylearn pre-trained models
        url = 'https://api.monkeylearn.com/v3/classifiers/'
        response = requests.get(url, headers={'Authorization': 'Token {}'.format(API_key)})
        if response.status_code == 200:
            models = response.json()
            models_list = [model['id'] for model in models]
        else:
            raise Exception(f"Server response {response.status_code}")

        if model_id not in models_list:
            raise Exception(f"Model_id {model_id} not found in MonkeyLearn pre-trained models")

        self.model_storage.json_set('args',args)

        def predict(self, df, args=None):
            args = self.model_storage.json_get('args')
            input_list = df[args['input_column']]
            ml = MonkeyLearn(args['YOUR_API_KEY'])
            classifier_response = ml.classifiers.classify(args['MODEL_ID'],input_list)
            df_dict = []
            for res_dict in classifier_response.body:
                text = res_dict['text']
                pred_dict = res_dict['classifications'][0]  #Only add the one which model is more confident about
                pred_dict['text'] = text
                df_dict.append(pred_dict)
            pred_df = pd.DataFrame(df_dict)
            return pred_df

        def describe(self, attribute: Optional[str] = None) -> pd.DataFrame:
            args = self.model_storage.json_get('args')
            ml = MonkeyLearn(args['YOUR_API_KEY'])










