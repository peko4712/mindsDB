from typing import Optional

import duckdb
from duckdb import CatalogException
import pandas as pd
import boto3
from botocore.exceptions import ClientError
import io
import ast

from mindsdb_sql import parse_sql
from mindsdb.integrations.libs.base import DatabaseHandler

from mindsdb_sql.parser.ast.base import ASTNode
from mindsdb_sql.parser.ast import Select, Identifier

from mindsdb.utilities import log
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE
)


logger = log.getLogger(__name__)

class S3Handler(DatabaseHandler):
    """
    This handler handles connection and execution of the S3 statements.
    """

    name = 's3'

    def __init__(self, name: str, connection_data: Optional[dict], **kwargs):
        """
        Initialize the handler.
        Args:
            name (str): name of particular handler instance
            connection_data (dict): parameters for connecting to the database
            **kwargs: arbitrary keyword arguments.
        """
        super().__init__(name)
        self.parser = parse_sql
        self.dialect = 's3'
        self.connection_data = connection_data
        self.kwargs = kwargs

        self.connection = None
        self.is_connected = False

        self.is_select_query = False
        self.key = None
        self.table_name = 's3_table'

    def __del__(self):
        if self.is_connected is True:
            self.disconnect()

    def connect(self) -> StatusResponse:
        """
        Set up the connection required by the handler.
        Returns:
            HandlerStatusResponse
        """

        if self.is_connected is True:
            return self.connection

        # Validate mandatory parameters.
        if not all(key in self.connection_data for key in ['aws_access_key_id', 'aws_secret_access_key', 'bucket']):
            raise ValueError('Required parameters (aws_access_key_id, aws_secret_access_key, bucket) must be provided.')

        # Connect to S3 via DuckDB and configure mandatory credentials.
        self.connection = self._connect_duckdb()

        self.is_connected = True

        return self.connection
    
    def _connect_duckdb(self):
        # Connect to S3 via DuckDB.
        duckdb_conn = duckdb.connect()
        duckdb_conn.execute("INSTALL httpfs")
        duckdb_conn.execute("LOAD httpfs")

        # Configure mandatory credentials.
        duckdb_conn.execute(f"SET s3_access_key_id='{self.connection_data['aws_access_key_id']}'")
        duckdb_conn.execute(f"SET s3_secret_access_key='{self.connection_data['aws_secret_access_key']}'")

        # Configure optional parameters.
        if 'aws_session_token' in self.connection_data:
            duckdb_conn.execute(f"SET s3_session_token='{self.connection_data['aws_session_token']}'")

        if 'region' in self.connection_data:
            duckdb_conn.execute(f"SET s3_region='{self.connection_data['region']}'")

        return duckdb_conn
    
    def _connect_boto3(self):
        # Configure mandatory credentials.
        config = {
            'aws_access_key_id': self.connection_data['aws_access_key_id'],
            'aws_secret_access_key': self.connection_data['aws_secret_access_key']
        }

        # Configure optional parameters.
        if 'aws_session_token' in self.connection_data:
            config['aws_session_token'] = self.connection_data['aws_session_token']

        if 'region_name' in self.connection_data:
            config['region_name'] = self.connection_data['region']

        return boto3.client('s3', **config)

    def disconnect(self):
        """ Close any existing connections
        Should switch self.is_connected.
        """
        if not self.is_connected:
            return
        self.connection.close()
        self.is_connected = False

    def check_connection(self) -> StatusResponse:
        """
        Check connection to the handler.
        Returns:
            HandlerStatusResponse
        """

        response = StatusResponse(False)
        need_to_close = self.is_connected is False

        # Check connection via boto3.
        try:
            boto3_conn = self._connect_boto3()
            boto3_conn.head_bucket(Bucket=self.connection_data['bucket'])
            response.success = True
        except ClientError as e:
            logger.error(f'Error connecting to S3 with the given credentials, {e}!')
            response.error_message = str(e)

        # TODO: Check connection via DuckDB?

        if response.success and need_to_close:
            self.disconnect()

        elif not response.success and self.is_connected:
            self.is_connected = False

        return response

    def native_query(self, query: str) -> StatusResponse:
        """
        Receive raw query and act upon it somehow.
        Args:
            query (str): query in native format
        Returns:
            HandlerResponse
        """

        need_to_close = not self.is_connected

        connection = self.connect()
        cursor = connection.cursor()

        try:
            self._create_table_from_file()

            cursor.execute(query)
            if self.is_select_query:
                result = cursor.fetchall()
                if result:
                    response = Response(
                        RESPONSE_TYPE.TABLE,
                        data_frame=pd.DataFrame(
                            result,
                            columns=[x[0] for x in cursor.description]
                        )
                    )

            else:
                connection.commit()
                self._write_table_to_file()
                response = Response(RESPONSE_TYPE.OK)
        except Exception as e:
            logger.error(f'Error running query: {query} on {self.connection_data["bucket"]}, {e}!')
            response = Response(
                RESPONSE_TYPE.ERROR,
                error_message=str(e)
            )

        if need_to_close is True:
            self.disconnect()

        return response
    
    def _create_table_from_file(self):
        connection = self.connect()
        try:
            connection.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM 's3://{self.connection_data['bucket']}/{self.key}'")
        except CatalogException as e:
            logger.error(f'Error creating table {self.table_name} from file {self.key} in {self.connection_data["bucket"]}, {e}!')
            raise e

    def _write_table_to_file(self):
        try:
            connection = self.connect()
            connection.execute(f"COPY {self.table_name} to 's3://{self.connection_data['bucket']}/{self.key}'")
        except CatalogException as e:
            logger.error(f'Error writing table {self.table_name} to file {self.key} in {self.connection_data["bucket"]}, {e}!')
            raise e

    def query(self, query: ASTNode) -> StatusResponse:
        """
        Receive query as AST (abstract syntax tree) and act upon it somehow.
        Args:
            query (ASTNode): sql query represented as AST. May be any kind
                of query: SELECT, INTSERT, DELETE, etc
        Returns:
            HandlerResponse
        """
        if isinstance(query, Select):
            self.is_select_query = True
            table = query.from_table

            query.from_table = Identifier(
                parts=[self.table_name],
                alias=table.alias
            )

        else:
            table = query.table

            query.table = Identifier(
                parts=[self.table_name],
                alias=table.alias
            )

        self.key = table.get_string().replace('`', '')

        return self.native_query(query.to_string())

    def get_tables(self) -> StatusResponse:
        """
        Return list of entities that will be accessible as tables.
        Returns:
            HandlerResponse
        """

        connection = self.connect()
        objects = [obj['Key'] for obj in connection.list_objects(Bucket=self.connection_data["bucket"])['Contents']]

        response = Response(
            RESPONSE_TYPE.TABLE,
            data_frame=pd.DataFrame(
                objects,
                columns=['table_name']
            )
        )

        return response

    def get_columns(self) -> StatusResponse:
        """
        Returns a list of entity columns.
        Args:
            table_name (str): name of one of tables returned by self.get_tables()
        Returns:
            HandlerResponse
        """

        query = "SELECT * FROM S3Object LIMIT 5"
        result = self.native_query(query)

        response = Response(
            RESPONSE_TYPE.TABLE,
            data_frame=pd.DataFrame(
                {
                    'column_name': result.data_frame.columns,
                    'data_type': result.data_frame.dtypes
                }
            )
        )

        return response
