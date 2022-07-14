# ---- Build proxygen with all the dependencies ----
FROM ubuntu:focal AS builder
ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /usr/src/app

RUN apt-get update &&         \
    apt-get install -y        \
    sudo                      \
    g++                       \
    make                      \
    cmake                     \
    git                       \
    m4                        \
    pkg-config                \
    libkrb5-dev               \
    libsasl2-dev              \
    libnuma-dev               \
    libboost-all-dev          \
    libevent-dev              \
    libdouble-conversion-dev  \
    libgoogle-glog-dev        \
    libgflags-dev             \
    libiberty-dev             \
    liblz4-dev                \
    liblzma-dev               \
    libsnappy-dev             \
    zlib1g-dev                \
    binutils-dev              \
    libjemalloc-dev           \
    libssl-dev                \
    libcap-dev                \
    libsodium-dev             \
    libtool                   \
    flex                      \
    bison                     \
    gperf                     \
    wget                      \
    unzip

# Invalidate cache if there are new commits w.r.t. the last build
ADD https://api.github.com/repos/diegocasu/proxygen/git/refs/heads/main version.json
RUN git clone https://github.com/diegocasu/proxygen
WORKDIR ./proxygen/proxygen

# Build proxygen without tests
RUN chmod +x ./build.sh && ./build.sh --with-quic --no-tests

# Save shared libs
RUN ldd ./_build/proxygen/httpserver/mhq | grep "=> /" | awk '{print $3}' > libs.txt
RUN tar cvf libs.tar --dereference --files-from=libs.txt

# ---- Build minimal image----
FROM ubuntu:focal AS mhq

# Copy and extract shared libraries
COPY --from=builder /usr/src/app/proxygen/proxygen/libs.tar /
RUN tar xvf libs.tar && rm libs.tar

# Copy client executable
WORKDIR /usr/src/app/proxygen
COPY --from=builder /usr/src/app/proxygen/proxygen/_build/proxygen/httpserver/mhq ./
ENTRYPOINT ["./mhq"]
