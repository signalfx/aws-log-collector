FROM public.ecr.aws/lambda/python:3.7

ARG AWS_DEFAULT_REGION
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY

ENV AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
ENV AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
ENV AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

COPY ./aws_log_collector aws_log_collector
COPY ./tests tests
COPY function.py .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["function.lambda_handler"]