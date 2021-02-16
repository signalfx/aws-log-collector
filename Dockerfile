FROM public.ecr.aws/lambda/python:3.7
COPY ./aws_log_collector aws_log_collector
COPY function.py .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["function.lambda_handler"]