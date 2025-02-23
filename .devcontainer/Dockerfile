FROM python:latest

RUN pip install --no-cache --upgrade build

WORKDIR /workspaces/compass_toolkit
ADD . .
RUN make install
