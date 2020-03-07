import inspect
import logging
import datetime as dt
import math
from sqlalchemy.sql.sqltypes import TIMESTAMP,VARCHAR
import numpy as np
import pandas as pd
import json
import base64
import requests

#from iotfunctions.base import BaseTransformer
from iotfunctions.base import BasePreload
from iotfunctions import ui
from iotfunctions.db import Database
from iotfunctions import bif
#import datetime as dt
import datetime
import urllib3
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# Specify the URL to your package here.
# This URL must be accessible via pip install
#PACKAGE_URL = 'git+https://github.com/madendorff/functions@'
PACKAGE_URL = 'git+https://github.com/kkbankol-ibm/monitor-anomaly@'

class InvokeExternalModel(BasePreload):
    '''
    Load entity data, forward to a custom anomaly detection model hosted in Watson Machine Learning service.
    Response returns index of rows that are classified as an anomaly, as well as the confidence score
    '''

    out_table_name = None

    def __init__(self, wml_endpoint, uid, password, instance_id, apikey, headers = None, body = None, column_map = None, output_item  = 'http_preload_done'):
    # def __init__(self, model_url, headers = None, body = None, column_map = None, output_item  = 'http_preload_done'):
        if body is None:
            body = {}

        if headers is None:
            headers = {}

        if column_map is None:
            column_map = {}

        super().__init__(dummy_items=[],output_item = output_item)

        # create an instance variable with the IBM IOT Platform Analytics Service Function input arguments.

        self.body = body
        logging.debug('body %s' %body)
        self.column_map = column_map
        logging.debug('column_map %s' %column_map)
        self.wml_endpoint = wml_endpoint
        self.uid = uid
        self.password = password
        self.instance_id = instance_id
        self.apikey = apikey



    '''
    def invoke_model(self, df):
        logging.debug('invoking model')
        model_url = self.model_url
        body = df #.to_dict()
        logging.debug('posting dataframe %s' %str(body))
        logging.debug('target %s' %model_url)
        # print("posting following dataframe")
        # print(body)
        # here we need to filter down to the specific fields the user wants.
        return []
        r = requests.post(model_url, json=body)
        if r.status_code == 200:
            logging.debug("predictions received")
            predictions = r.json()
            logging.debug("predictions")
            logging.debug(predictions)
            return predictions
        else:
            logging.debug("failure receiving predictions")
            logging.debug(r.status_code)
            logging.debug(r.text)
            return []
    '''

    def invoke_model(self, df, wml_endpoint, uid, password, instance_id, apikey):
        # Taken from https://github.ibm.com/Shuxin-Lin/anomaly-detection/blob/master/Invoke-WML-Scoring.ipynb
        # Get an IAM token from IBM Cloud
        print("posting enitity data to WML model")
        url     = "https://iam.bluemix.net/oidc/token"
        headers = { "Content-Type" : "application/x-www-form-urlencoded" }
        data    = "apikey=" + apikey + "&grant_type=urn:ibm:params:oauth:grant-type:apikey"
        response  = requests.post( url, headers=headers, data=data, auth=( uid, password ) )
        if 200 != response.status_code:
            logging.error('error getting IAM token')
            logging.error( response.status_code )
            logging.error( response.reason )
            return []
        else:
            logging.debug('token successfully generated')
            iam_token = response.json()["access_token"]
            # Send data to deployed model for processing
            headers = { "Content-Type" : "application/json",
                        "Authorization" : "Bearer " + iam_token,
                        "ML-Instance-ID" : instance_id }
            logging.debug("posting to WML")
            payload = df.to_dict()
            r = requests.post( wml_endpoint, json=payload, headers=headers )
            if r.status_code == 200:
                j = r.json()
                logging.debug('model response')
                logging.debug(j)
                return j
            else:
                logging.error(r.status_code)
                logging.error(r.text)
            # print ( response.text )

    def execute(self, df, start_ts = None,end_ts=None,entities=None):
        # TODO, set time range if not provided. Grab all rows within x hours
        logging.debug('in execution method')
        entity_type = self.get_entity_type()
        logging.debug('entity_type')
        logging.debug(entity_type)
        self.db = entity_type.db
        logging.debug('entity db')
        # encoded_body = json.dumps(self.body).encode('utf-8')
        # encoded_headers = json.dumps(self.headers).encode('utf-8')

        # This class is setup to write to the entity time series table
        # To route data to a different table in a custom function,
        # you can assign the table name to the out_table_name class variable
        # or create a new instance variable with the same name

        if self.out_table_name is None:
            table = entity_type.name
        else:
            table = self.out_table_name
        logging.debug('set table')
        schema = entity_type._db_schema
        logging.debug('schema')


        response_data = {}
        (metrics,dates,categoricals,others) = self.db.get_column_lists_by_type(
            table = table,
            schema= schema,
            exclude_cols = []
        )
        # TODO, can't we also get calculated metrics?
        logging.debug('all metrics %s ' %metrics)

        # TODO, grabbing all table data for now, add logic to break up by entity id and use start/end_ts values.
        table_data = self.db.read_table(table_name=table, schema=schema)
        logging.debug('table_data')
        logging.debug(table_data)
        # rows = len(buildings)

        # for m in metrics:
        #     logging.debug('metrics %s ' %m)
        #     # response_data[m] = np.random.normal(0,1,rows)
        #     logging.debug('metrics data %s ' %response_data[m])
        #
        # for d in dates:
        #     logging.debug('dates %s ' %d)
        #     response_data[d] = dt.datetime.utcnow() - dt.timedelta(seconds=15)
        #     logging.debug('dates data %s ' %response_data[d])

        '''
        # Create a timeseries dataframe with data received from Maximo
        '''
        logging.debug('response_data used to create dataframe ===' )
        logging.debug( response_data)
        # df = pd.DataFrame(data=response_data)
        df = table_data

        results = self.invoke_model(df, self.wml_endpoint, self.uid, self.password, self.instance_id, self.apikey)
        if results:
            logging.debug('results %s' %results )
        else:
            logging.error('error invoking external model')

        logging.debug('Generated DF from response_data ===' )
        logging.debug( df.head() )
        df = df.rename(self.column_map, axis='columns')
        logging.debug('ReMapped DF ===' )
        logging.debug( df.head() )

        '''
        # Fill in missing columns with nulls
        '''
        required_cols = self.db.get_column_names(table = table, schema=schema)
        logging.debug('required_cols %s' %required_cols )
        missing_cols = list(set(required_cols) - set(df.columns))
        logging.debug('missing_cols %s' %missing_cols )
        if len(missing_cols) > 0:
            kwargs = {
                'missing_cols' : missing_cols
            }
            entity_type.trace_append(created_by = self,
                                     msg = 'http data was missing columns. Adding values.',
                                     log_method=logger.debug,
                                     **kwargs)
            for m in missing_cols:
                if m==entity_type._timestamp:
                    df[m] = dt.datetime.utcnow() - dt.timedelta(seconds=15)
                elif m=='devicetype':
                    df[m] = entity_type.logical_name
                else:
                    df[m] = None

        '''
        # Remove columns that are not required
        '''
        df = df[required_cols]
        logging.debug('DF stripped to only required columns ===' )
        logging.debug( df.head() )

        '''
        # Write the dataframe to the IBM IOT Platform database table
        '''
        # TODO, need to adjust this logic, possibly to add a column specifying whether row is an anomaly or not?
        # Or write to seperate table

        # self.write_frame(df=df, table_name=table)

        # anomaly_table = "anomalies"
        # self.db.create(anomaly_table)
        # self.write_frame(df=df, table_name=anomaly_table)

        kwargs ={
            'table_name' : table,
            'schema' : schema,
            'row_count' : len(df.index)
        }
        logging.debug( "write_frame complete" )
        entity_type.trace_append(created_by=self,
                                 msg='Wrote data to table',
                                 log_method=logger.debug,
                                 **kwargs)
        logging.debug( "appended trace" )
        return True

    '''
    # Create the IOT Platform Function User Interfact input arguements used to connect to the external REST Service.
    # These could be used to connect with any Rest Service to get IOT Data or any other data to include in your dashboards.
    '''
    @classmethod
    def build_ui(cls):
        '''
        Registration metadata
        '''
        # define arguments that behave as function inputs
        inputs = []
        inputs.append(ui.UISingle(name='wml_endpoint',
                              datatype=str,
                              description='Endpoint to WML service where model is hosted',
                              tags=['TEXT'],
                              required=True
                              ))
        inputs.append(ui.UISingle(name='uid',
                              datatype=str,
                              description='IBM Cloud IAM User ID',
                              tags=['TEXT'],
                              required=True
                              ))
        inputs.append(ui.UISingle(name='password',
                              datatype=str,
                              description='IBM Cloud IAM Password',
                              tags=['TEXT'],
                              required=True
                              ))
        inputs.append(ui.UISingle(name='instance_id',
                              datatype=str,
                              description='Instance ID for WML model',
                              tags=['TEXT'],
                              required=True
                              ))
        inputs.append(ui.UISingle(name='apikey',
                              datatype=str,
                              description='IBM Cloud API Key',
                              tags=['TEXT'],
                              required=True
                              ))
        # define arguments that behave as function outputs
        outputs=[]
        outputs.append(ui.UIStatusFlag(name='output_item'))
        return (inputs, outputs)