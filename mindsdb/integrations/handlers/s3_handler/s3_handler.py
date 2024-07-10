import boto3
import duckdb
import pandas as pd
from typing import Text, Dict, Optional
from botocore.exceptions import ClientError
from duckdb import DuckDBPyConnection, CatalogException

from mindsdb_sql.parser.ast.base import ASTNode
from mindsdb_sql.parser.ast import Select, Identifier

from mindsdb.utilities import log
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE
)

from mindsdb.integrations.libs.base import DatabaseHandler


logger = log.getLogger(__name__)

class S3Handler(DatabaseHandler):
    """
    This handler handles connection and execution of the SQL statements on AWS S3.
    """

    name = 's3'

    def __init__(self, name: Text, connection_data: Optional[Dict], **kwargs):
        """
        Initializes the handler.

        Args:
            name (Text): The name of the handler instance.
            connection_data (Dict): The connection data required to connect to the AWS (S3) account.
            kwargs: Arbitrary keyword arguments.
        """
        super().__init__(name)
        self.connection_data = connection_data
        self.kwargs = kwargs
        self.key = None

        self.connection = None
        self.is_connected = False

        self.is_select_query = False
        self.key = None
        self.table_name = 's3_table'

    def __del__(self):
        if self.is_connected is True:
            self.disconnect()

    def connect(self) -> DuckDBPyConnection:
        """
        Establishes a connection to the AWS (S3) account via DuckDB.

        Raises:
            KeyError: If the required connection parameters are not provided.
            
        Returns:
            boto3.client: A client object to the AWS (S3) account.
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
    
    def _connect_duckdb(self) -> DuckDBPyConnection:
        """
        Establishes a connection to the AWS (S3) account via DuckDB.

        Returns:
            DuckDBPyConnection: A connection object to the AWS (S3) account.
        """
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
    
    def _connect_boto3(self) -> boto3.client:
        """
        Establishes a connection to the AWS (S3) account via boto3.

        Returns:
            boto3.client: A client object to the AWS (S3) account.
        """
        # Configure mandatory credentials.
        config = {
            'aws_access_key_id': self.connection_data['aws_access_key_id'],
            'aws_secret_access_key': self.connection_data['aws_secret_access_key']
        }

        # Configure optional parameters.
        if 'aws_session_token' in self.connection_data:
            config['aws_session_token'] = self.connection_data['aws_session_token']

        # DuckDB considers us-east-1 to be the default region.
        config['region_name'] = self.connection_data['region'] if 'region' in self.connection_data else 'us-east-1'

        return boto3.client('s3', **config)

    def disconnect(self):
        """
        Closes the connection to the AWS (S3) account if it's currently open.
        """
        if not self.is_connected:
            return
        self.connection.close()
        self.is_connected = False

    def check_connection(self) -> StatusResponse:
        """
        Checks the status of the connection to the S3 bucket.

        Returns:
            StatusResponse: An object containing the success status and an error message if an error occurs.
        """
        response = StatusResponse(False)
        need_to_close = self.is_connected is False

        # Check connection via boto3.
        try:
            boto3_conn = self._connect_boto3()
            result = boto3_conn.head_bucket(Bucket=self.connection_data['bucket'])

            # Check if the bucket is in the same region as specified: the DuckDB connection will fail otherwise.
            if result['ResponseMetadata']['HTTPHeaders']['x-amz-bucket-region'] != boto3_conn.meta.region_name:
                raise ValueError('The bucket is not in the expected region.')
            response.success = True
        except (ClientError, ValueError) as e:
            logger.error(f'Error connecting to S3 with the given credentials, {e}!')
            response.error_message = str(e)

        # TODO: Check connection via DuckDB?

        if response.success and need_to_close:
            self.disconnect()

        elif not response.success and self.is_connected:
            self.is_connected = False

        return response

    def native_query(self, query: Text) -> Response:
        """
        Executes a SQL query on the specified table (object) in the S3 bucket.

        Args:
            query (Text): The SQL query to be executed.

        Returns:
            Response: A response object containing the result of the query or an error message.
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
    
    def _create_table_from_file(self) -> None:
        """
        Creates a table from a file in the S3 bucket.

        Raises:
            CatalogException: If the file does not exist in the S3 bucket.
        """
        connection = self.connect()
        try:
            connection.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM 's3://{self.connection_data['bucket']}/{self.key}'")
        except CatalogException as e:
            logger.error(f'Error creating table {self.table_name} from file {self.key} in {self.connection_data["bucket"]}, {e}!')
            raise e

    def _write_table_to_file(self) -> None:
        """
        Writes the table to a file in the S3 bucket.

        Raises:
            CatalogException: If the table does not exist in the DuckDB connection.
        """
        try:
            connection = self.connect()
            connection.execute(f"COPY {self.table_name} to 's3://{self.connection_data['bucket']}/{self.key}'")
        except CatalogException as e:
            logger.error(f'Error writing table {self.table_name} to file {self.key} in {self.connection_data["bucket"]}, {e}!')
            raise e

    def query(self, query: ASTNode) -> Response:
        """
        Executes a SQL query represented by an ASTNode and retrieves the data.

        Args:
            query (ASTNode): An ASTNode representing the SQL query to be executed.

        Returns:
            Response: The response from the `native_query` method, containing the result of the SQL query execution.
        """
        # Set the key (file) by getting it from the query.
        # This will be used to create a table from the file in the S3 bucket.
        # Replace the key with the name of the table to be created.
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

        # Check if the file exists in the S3 bucket.
        try:
            boto3_conn = self._connect_boto3()
            boto3_conn.head_object(Bucket=self.connection_data['bucket'], Key=self.key)
        except ClientError as e:
            logger.error(f'The file {self.key} does not exist in the bucket {self.connection_data["bucket"]}: {e}!')
            raise ValueError(f'The file {self.key} does not exist in the bucket {self.connection_data["bucket"]}!')

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
