import aws_cdk as cdk
import aws_cdk.aws_s3 as _s3
import aws_cdk.aws_sqs as _sqs
import aws_cdk.aws_iam as _iam
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_s3_notifications as _s3n
import aws_cdk.aws_sns as _sns
import aws_cdk.aws_sns_subscriptions as _snssubscr
import aws_cdk.aws_stepfunctions as _sfn
import aws_cdk.aws_stepfunctions_tasks as _tasks

import aws_cdk.aws_events as _events
import aws_cdk.aws_events_targets as _targets
from aws_cdk.aws_lambda_event_sources import (S3EventSource, SqsEventSource, SnsEventSource, DynamoEventSource)
from aws_cdk import aws_events, aws_events_targets

from config import IDs, EnvSettings, Name, ARNs, ResourceNames

class TrainingPipelineStack(cdk.Stack):

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)


        # The code that defines your stack goes here
        '''******************************SNS Topics****************************** '''
        jobCompletionTopic = _sns.Topic(self, 'jobCompletion')

        '''******************************IAM Roles****************************** '''

        textractServiceRole = _iam.Role(self, 'TextractServiceRole', assumed_by=_iam.ServicePrincipal('textract'
                                                                                                      '.amazonaws.com'))
        textractServiceRole.add_to_policy(_iam.PolicyStatement(effect=_iam.Effect.ALLOW,
                                                               actions=["sns:Publish"],
                                                               resources=[jobCompletionTopic.topic_arn]))

        '''******************************S3 Bucket****************************** '''
        # Create raw and textract output S3 buckets
        raw_bucket = _s3.Bucket(self, 'raw_bucket',
                                bucket_name=EnvSettings.INPUT_BUCKET_NAME,
                                auto_delete_objects=True,
                                removal_policy=cdk.RemovalPolicy.DESTROY,
                                lifecycle_rules=[_s3.LifecycleRule(
                                    transitions=[_s3.Transition(
                                        storage_class=_s3.StorageClass.GLACIER,
                                        transition_after=cdk.Duration.days(7))]
                                )])

        # merged output bucket
        merged_output_bucket = _s3.Bucket(self, 'merged_output_bucket',
                                            bucket_name=EnvSettings.MERGED_OUTPUT_BUCKET_NAME,
                                            auto_delete_objects=True,
                                            removal_policy=cdk.RemovalPolicy.DESTROY)

        # textract output bucket
        textract_output_bucket = _s3.Bucket(self, 'textract_output_bucket',
                                            bucket_name=EnvSettings.TEXTRACT_OUTPUT_BUCKET_NAME,
                                            auto_delete_objects=True,
                                            removal_policy=cdk.RemovalPolicy.DESTROY)

        '''******************************SQS****************************** '''
        # DLQ
        dlq = _sqs.Queue(self, 'DLQ', visibility_timeout=cdk.Duration.seconds(30),
                         retention_period=cdk.Duration.seconds(1209600))

        # Queue for async jobs
        inputDocQueue = _sqs.Queue(self, 'InputDocs',
                                   queue_name='input_job_queue-1',
                                   visibility_timeout=cdk.Duration.seconds(90),
                                   retention_period=cdk.Duration.seconds(1209600),
                                   dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                   )
        # Add notification events to the input bucket
        raw_bucket.add_event_notification(_s3.EventType.OBJECT_CREATED, _s3n.SqsDestination(inputDocQueue),
                                          _s3.NotificationKeyFilter(prefix="uploads", suffix=".pdf", )
                                          )


        # Queue for async Textract jobs results
        jobResultsQueue = _sqs.Queue(self, 'JobResults',
                                     queue_name='job_results_queue',
                                     visibility_timeout=cdk.Duration.seconds(300),
                                     retention_period=cdk.Duration.seconds(1209600),
                                     dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                     )
        # Trigger between SNS -> SQS once Textract job is completed
        jobCompletionTopic.add_subscription(_snssubscr.SqsSubscription(jobResultsQueue))

        # Queue for async jobs
        textractLimitQueue = _sqs.Queue(self, 'TextractLimit',
                                   queue_name='textract_limit_queue',
                                   visibility_timeout=cdk.Duration.seconds(90),
                                   retention_period=cdk.Duration.seconds(1209600),
                                   dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                   )

        ## -----Test code starts from here

        # Pandas layer
        pandasLayer = _lambda.LayerVersion(self, 'PandasLayer',
                                           code=_lambda.Code.from_asset('assets/lambda/pdnp'),
                                           compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
                                           license='Apache-2.0',
                                           description='Pandas layer')
        # PyPDF2 layer
        pyPDF2Layer = _lambda.LayerVersion(self, 'PyPDF2Layer',
                                           code=_lambda.Code.from_asset('assets/lambda/PyPDF2'),
                                           compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
                                           license='Apache-2.0',
                                           description='PyPDF2 layer')

        ## --- State Machine

        # Lambda Handlers Definitions

        SplitLambda = _lambda.Function(self, 'SplitLambda',
                                       function_name='split_file_lambda',
                                       description="Function to split the files in smaller chunks",
                                       runtime=_lambda.Runtime.PYTHON_3_7,
                                       handler='SplitLambda.lambda_handler',
                                       layers=[pyPDF2Layer],
                                       code=_lambda.Code.from_asset('assets/lambda/textractworkaround'),
                                       timeout=cdk.Duration.seconds(900),
                                       # memory=10240,
                                       retry_attempts=0,
                                       environment={
                                           'tmp_bucket_name': merged_output_bucket.bucket_name
                                       }
                                       )
        raw_bucket.grant_read_write(SplitLambda)
        merged_output_bucket.grant_read_write(SplitLambda)


        StartTextractJobLambda = _lambda.Function(self, 'StartTextractJobLambda',
                                                  function_name='start_textract_job_lambda',
                                                  description="Function to kick-off textract Job for smaller chunks",
                                                  runtime=_lambda.Runtime.PYTHON_3_7,
                                                  handler='StartTextractJobLambda.lambda_handler',
                                                  code=_lambda.Code.from_asset('assets/lambda/textractworkaround/'),
                                                  timeout=cdk.Duration.seconds(300),
                                                  retry_attempts=0
                                                  )
        merged_output_bucket.grant_read_write(StartTextractJobLambda)

        StartTextractJobLambda.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                                       resources=[textractServiceRole.role_arn]))
        StartTextractJobLambda.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                                       resources=["*"]))

        CheckJobStatusLambda = _lambda.Function(self, 'CheckJobStatusLambda',
                                                function_name='check_job_status_lambda',
                                                description="Function to check the Textract job status",
                                                runtime=_lambda.Runtime.PYTHON_3_7,
                                                handler='CheckJobStatusLambda.lambda_handler',
                                                code=_lambda.Code.from_asset('assets/lambda/textractworkaround/'),
                                                timeout=cdk.Duration.seconds(900),
                                                retry_attempts=0
                                                )
        CheckJobStatusLambda.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                                     resources=[textractServiceRole.role_arn]))
        CheckJobStatusLambda.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                                     resources=["*"]))


        MergeLambda = _lambda.Function(self, 'MergeLambda',
                                       function_name='merge_lambda',
                                       description="Function to Merge the textract results",
                                       runtime=_lambda.Runtime.PYTHON_3_7,
                                       handler='MergeLambda.lambda_handler',
                                       code=_lambda.Code.from_asset('assets/lambda/textractworkaround/'),
                                       timeout=cdk.Duration.seconds(900),
                                       retry_attempts=0,
                                       environment={'merge_output_bucket': merged_output_bucket.bucket_name
                                                    }
                                       )

        merged_output_bucket.grant_read_write(MergeLambda)
        MergeLambda.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                            resources=[textractServiceRole.role_arn]))
        MergeLambda.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                            resources=["*"]))

        # Step functions Definition

        split_job = _tasks.LambdaInvoke(
            self, "Split Job",
            lambda_function=SplitLambda,
            output_path="$.Payload",
        )
        start_textract_job = _tasks.LambdaInvoke(
            self, "Start Textract Job",
            lambda_function=StartTextractJobLambda,
            output_path="$.Payload",
        )

        wait_job = _sfn.Wait(
            self, "Wait 1 Minute",
            time=_sfn.WaitTime.duration(
                cdk.Duration.seconds(60))
        )

        status_job = _tasks.LambdaInvoke(
            self, "Get Textract Job Status",
            lambda_function=CheckJobStatusLambda,
            output_path="$.Payload",
        )

        fail_job = _sfn.Fail(
            self, "Fail",
            cause='AWS Batch Job Failed',
            error='DescribeJob returned FAILED'
        )

        # succeed_job = _sfn.Succeed(
        #     self, "Succeeded",
        #     comment='AWS Batch Job succeeded'
        # )

        merge_textract_output = _tasks.LambdaInvoke(
            self, "Merge Textract Json Output",
            lambda_function=MergeLambda,
            output_path="$.Payload",
        )

        # Create Chain

        definition = split_job.next(start_textract_job) \
            .next(wait_job) \
            .next(status_job) \
            .next(_sfn.Choice(self, 'All Job Complete?')
                  .when(_sfn.Condition.string_equals('$.JobStatus', 'FAILED'), fail_job)
                  .when(_sfn.Condition.string_equals('$.status', 'SUCCEEDED'), merge_textract_output)
                  .otherwise(wait_job))

        # Create state machine
        sm = _sfn.StateMachine(
            self, "StateMachine",
            definition=definition,
            timeout=cdk.Duration.minutes(5),
        )

        # Lambda function to process Testing

        '''------------------------------------------------------------'''
        # Function to process events from input sqs
        InputSQSProcLambda = _lambda.Function(self, 'InputSQSProcLambda',
                                              function_name='input_sqs_msg_processor',
                                              description='Function to process messages from input queue',
                                              runtime=_lambda.Runtime.PYTHON_3_7,
                                              handler='InputSqsProcLambda.lambda_handler',
                                              code=_lambda.Code.from_asset('assets/lambda'),
                                              timeout=cdk.Duration.seconds(60),
                                              retry_attempts=0,
                                              reserved_concurrent_executions=5,
                                              layers=[pyPDF2Layer],
                                              environment={
                                                            'SNS_TOPIC_ARN': jobCompletionTopic.topic_arn,
                                                            'SNS_ROLE_ARN': textractServiceRole.role_arn,
                                                            'limit_qUrl': textractLimitQueue.queue_url
                                                            }
                                              )

        # Permissions
        raw_bucket.grant_read_write(InputSQSProcLambda)
        inputDocQueue.grant_consume_messages(InputSQSProcLambda)
        textractLimitQueue.grant_send_messages(InputSQSProcLambda)
        InputSQSProcLambda.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                               resources=[textractServiceRole.role_arn]))
        InputSQSProcLambda.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                               resources=["*"]))

        # Add Trigger between input sqs (input sqs)  and lambda
        InputSQSProcLambda.add_event_source(SqsEventSource(queue=inputDocQueue))

        '''------------------------------------------------------------'''
        # Function to process message from limit exceed queue and kick-off step function
        TextractLimitProcessor = _lambda.Function(self, 'TextractLimitProcessor',
                                              function_name='textract_limit_processor',
                                              description='Function to process messages from HL queue',
                                              runtime=_lambda.Runtime.PYTHON_3_7,
                                              handler='TextractHLProcLambda.lambda_handler',
                                              code=_lambda.Code.from_asset('assets/lambda'),
                                              timeout=cdk.Duration.seconds(60),
                                              retry_attempts=0,
                                              reserved_concurrent_executions=5,
                                              environment={
                                                  'qUrl': textractLimitQueue.queue_url,
                                                  "STATE_MACHINE_ARN": sm.state_machine_arn
                                              }
                                              )

        # Permissions
        raw_bucket.grant_read_write(TextractLimitProcessor)
        textractLimitQueue.grant_consume_messages(TextractLimitProcessor)
        TextractLimitProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                                   resources=[textractServiceRole.role_arn]))
        TextractLimitProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                                   resources=["*"]))
        TextractLimitProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["StepFunction:*"],
                                                                       resources=["*"]))
        TextractLimitProcessor.add_event_source(SqsEventSource(queue=textractLimitQueue))
        sm.grant_start_execution(TextractLimitProcessor)

        '''------------------------------------------------------------'''

        # Lambda function to process Textract output result

        jobResultProcessor = _lambda.Function(self, 'JobResultProcessor',
                                              function_name='job_result_processor',
                                              description="Function to generate final textract output",
                                              runtime=_lambda.Runtime.PYTHON_3_7,
                                              handler='ResultProcLambda.lambda_handler',
                                              code=_lambda.Code.from_asset('assets/lambda'),
                                              timeout=cdk.Duration.seconds(300),
                                              retry_attempts=0,
                                              reserved_concurrent_executions=5,
                                              layers=[pandasLayer],
                                              environment={'bucketName': textract_output_bucket.bucket_name,
                                                           'PREFIX': 'textract-output',
                                                           'qUrl': jobResultsQueue.queue_url
                                                           }
                                              )


        # Permission
        textract_output_bucket.grant_write(jobResultProcessor)
        jobResultsQueue.grant_consume_messages(jobResultProcessor)
        jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                                   resources=[textractServiceRole.role_arn]))
        jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                                   resources=["*"]))
        merged_output_bucket.add_event_notification(_s3.EventType.OBJECT_CREATED,
                                                 _s3n.LambdaDestination(jobResultProcessor),
                                                 _s3.NotificationKeyFilter(prefix="", suffix=".json"))

        # Add Trigger between sqs (where textract sns pushes messages) and lambda

        '''Note: batchSize: Determines how many records are buffered before invoking your lambda function.
        if using batchwindow- then apply recommended visibility timeout
        https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#events-sqs-queueconfig'''

        jobResultProcessor.add_event_source(SqsEventSource(queue=jobResultsQueue))
        # -----test code ends here