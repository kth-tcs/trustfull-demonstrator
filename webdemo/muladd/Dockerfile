FROM ubuntu:latest

RUN apt-get update -qq \
    && apt-get install -y build-essential wget

RUN wget https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-12/wasi-sdk_12.0_amd64.deb \
    && dpkg -i *.deb \
    && rm -f *.deb

ENTRYPOINT ["/opt/wasi-sdk/bin/clang"]
