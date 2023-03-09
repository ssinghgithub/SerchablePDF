#!/usr/bin/env python3
import sys

# caution: path[0] is reserved for script path (or '' in REPL)
sys.path.insert(1, '../src/')

from inspect import stack
import aws_cdk as cdk

from stacks.training_pipeline_stack import *
# from src.pipeline.train_pipeline_stack import TrainingPipelineStack
from config import IDs, EnvSettings, Name, ARNs, ResourceNames

app = cdk.App()
TrainingPipelineStack(app, Name.TRAINING_PIPELINE_STACK,
                      env=cdk.Environment(account=EnvSettings.ACCOUNT_ID, region=EnvSettings.ACCOUNT_REGION),
                      description='The Infrastructure for Training Pipeline'
                      )

app.synth()
