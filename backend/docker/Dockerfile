FROM public.ecr.aws/lambda/python:3.12

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Lambda handler and modules
COPY handler.py .
COPY html_parser.py .
COPY bedrock_classifier.py .
COPY bedrock_reviewer.py .
COPY screenshot_generator.py .
COPY image_annotator.py .
COPY pdf_builder.py .

CMD ["handler.lambda_handler"]
