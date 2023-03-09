from os import path
from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_lambda as lmb,
    aws_s3 as s3
)
from constructs import Construct
from ..pipeline.pipeline_bucket import InputBucket
from config import IDs, EnvSettings, Name, ARNs, ResourceNames


class TrainingPipelineStack(Stack):
    def __init__(self, scope, id, account,region,description):
        InputBucket(Stack, bucket_name=EnvSettings.INPUT_BUCKET_NAME)


    # def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
    #     super().__init__(scope, construct_id, **kwargs)
    #
    #     # The code that defines your stack goes here
    #
    #     inputBucket = InputBucket(scope, construct_id)
    #
    #     # example resource
    #     # queue = sqs.Queue(
    #     #     self, "IndexExtractionPipelineQueue",
    #     #     visibility_timeout=Duration.seconds(300),
    #     # )
    #
    #     this_dir = path.dirname(__file__)
    #
    #     # handler = lmb.Function(self, 'Handler',
    #     #                        runtime=lmb.Runtime.PYTHON_3_7,
    #     #                        handler='handler.handler',
    #     #                        code=lmb.Code.from_asset(path.join(this_dir, 'training_pipeline/lambda')))
