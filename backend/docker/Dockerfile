# Use the AWS Lambda Python 3.12 base image
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for Playwright/Chromium
RUN dnf install -y \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXi \
    libXrandr \
    libXScrnSaver \
    libXtst \
    pango \
    xorg-x11-fonts-100dpi \
    xorg-x11-fonts-75dpi \
    xorg-x11-fonts-cyrillic \
    xorg-x11-fonts-misc \
    xorg-x11-fonts-Type1 \
    xorg-x11-utils \
    alsa-lib \
    nss \
    nspr \
    && dnf clean all

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium to a fixed path that Lambda can access
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install chromium

# Copy Lambda handler and modules
COPY handler.py .
COPY html_parser.py .
COPY bedrock_classifier.py .
COPY bedrock_reviewer.py .
COPY screenshot_generator.py .
COPY image_annotator.py .
COPY pdf_builder.py .

CMD ["handler.lambda_handler"]
