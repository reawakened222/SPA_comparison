###############################################################################
#-----------------------------    BUILD STAGE   ------------------------------#
###############################################################################

FROM python:3.6-slim-stretch as builder

ARG CC_VERSION=master
ENV CC_VERSION ${CC_VERSION}

ARG DEBIAN_FRONTEND=noninteractive
RUN set -x && apt-get update -qq \
  && apt-get install -qqy --no-install-recommends \
    ca-certificates \
    curl \
    doxygen \
    git \
    make \
    && curl -sL https://deb.nodesource.com/setup_12.x | bash - \
    && apt-get install -y nodejs

# Download CodeChecker release.
RUN git clone https://github.com/Ericsson/CodeChecker.git /codechecker
WORKDIR /codechecker
RUN git checkout ${CC_VERSION}

# Build CodeChecker web.
RUN make -C /codechecker/web package

###############################################################################
#--------------------------    PRODUCTION STAGE   ----------------------------#
###############################################################################

FROM python:3.6-slim-stretch

ARG CC_GID=950
ARG CC_UID=950

ENV CC_GID ${CC_GID}
ENV CC_UID ${CC_UID}

ARG INSTALL_AUTH=yes
ARG INSTALL_PG8000=no
ARG INSTALL_PSYCOPG2=yes

ENV TINI_VERSION v0.18.0

RUN set -x && apt-get update -qq \
  # Prevent fail when install postgresql-client.
  && mkdir -p /usr/share/man/man1 \
  && mkdir -p /usr/share/man/man7 \
  \
  && apt-get install -qqy --no-install-recommends ca-certificates \
    postgresql-client \
    # To switch user and exec command.
    gosu

RUN if [ "$INSTALL_AUTH" = "yes" ] ; then \
      apt-get install -qqy --no-install-recommends \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev; \
    fi

RUN if [ "$INSTALL_PSYCOPG2" = "yes" ] ; then \
      apt-get install -qqy --no-install-recommends \
        libpq-dev; \
    fi

COPY --from=builder /codechecker/web/build/CodeChecker /codechecker

# Copy python requirements.
COPY --from=builder /codechecker/web/requirements_py /requirements_py
COPY --from=builder /codechecker/web/requirements.txt /requirements_py

# Install python requirements.
RUN apt-get install -qqy --no-install-recommends \
  python-dev \
  # gcc is needed to build psutil.
  gcc \
  \
  # Install necessary runtime environment files.
  && pip3 install -r /requirements_py/requirements.txt \
  && if [ "$INSTALL_AUTH" = "yes" ] ; then \
       pip3 install -r /requirements_py/auth/requirements.txt; \
     fi \
  && if [ "$INSTALL_PG8000" = "yes" ] ; then \
       pip3 install -r /requirements_py/db_pg8000/requirements.txt; \
     fi \
  && if [ "$INSTALL_PSYCOPG2" = "yes" ] ; then \
       pip3 install -r /requirements_py/db_psycopg2/requirements.txt; \
     fi \
  \
  # Remove unnecessary packages.
  && pip3 uninstall -y wheel \
  && apt-get purge -y --auto-remove \
    gcc \
    python-dev \
  \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/ \
  && set +x

# Create user and group for CodeChecker.
RUN groupadd -r codechecker -g ${CC_GID} \
  && useradd -r --no-log-init -M -u ${CC_UID} -g codechecker codechecker

# Change permission of the CodeChecker package.
RUN chown codechecker:codechecker /codechecker

ENV PATH="/codechecker/bin:$PATH"

COPY ./entrypoint.sh /usr/local/bin/
RUN chmod a+x /usr/local/bin/entrypoint.sh \
  && chown codechecker:codechecker /usr/local/bin/entrypoint.sh

ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

EXPOSE 8001

ENTRYPOINT ["/tini", "--", "/usr/local/bin/entrypoint.sh"]

# Experiment setup

# Install additional tools

### Frama-C ###
RUN apt install opam 

# 2. Install Frama-C's dependencies
RUN opam install depext
RUN opam depext frama-c

# 3. Install Frama-C itself
RUN opam install frama-c

RUN tar xzvf frama-clang-0.0.9.tar.gz
RUN cd frama-clang-0.0.9
RUN ./configure
RUN make
RUN make install

### Infer ###
FROM debian:buster-slim AS compilator

LABEL maintainer "Infer team"

# mkdir the man/man1 directory due to Debian bug #863199
RUN apt-get update && \
    mkdir -p /usr/share/man/man1 && \
    apt-get install --yes --no-install-recommends \
      autoconf \
      automake \
      bubblewrap \
      bzip2 \
      cmake \
      curl \
      g++ \
      gcc \
      git \
      libc6-dev \
      libgmp-dev \
      libmpfr-dev \
      libsqlite3-dev \
      make \
      openjdk-11-jdk-headless \
      patch \
      patchelf \
      pkg-config \
      python3.7 \
      python3-distutils \
      unzip \
      xz-utils \
      zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Install opam 2
RUN curl -sL https://github.com/ocaml/opam/releases/download/2.0.6/opam-2.0.6-x86_64-linux > /usr/bin/opam && \
    chmod +x /usr/bin/opam

# Disable sandboxing
# Without this opam fails to compile OCaml for some reason. We don't need sandboxing inside a Docker container anyway.
RUN opam init --reinit --bare --disable-sandboxing --yes --auto-setup

# Download the latest Infer master
RUN cd / && \
    git clone --depth 1 --recurse-submodules https://github.com/facebook/infer/

# Build opam deps first, then clang, then infer. This way if any step
# fails we don't lose the significant amount of work done in the
# previous steps.
RUN cd /infer && ./build-infer.sh --only-setup-opam
RUN cd /infer && \
    eval $(opam env) && \
    ./autogen.sh && \
    ./configure && \
    ./facebook-clang-plugins/clang/setup.sh

# Generate a release
RUN cd /infer && \
    make install-with-libs \
    BUILD_MODE=opt \
    PATCHELF=patchelf \
    DESTDIR="/infer-release" \
    libdir_relative_to_bindir="../lib"

FROM debian:buster-slim AS executor

RUN apt-get update && apt-get install --yes --no-install-recommends sqlite3

# Get the infer release
COPY --from=compilator /infer-release/usr/local /infer

# Installl infer
ENV PATH /infer/bin:${PATH}

# if called with /infer-host mounted then copy infer there
RUN if test -d /infer-host; then \
      cp -av /infer/. /infer-host; \
    fi