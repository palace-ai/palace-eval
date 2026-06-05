FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    wget git build-essential libffi-dev libtiff-dev \
    python3 python3-pip jq curl \
    locales locales-all tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget -q 'https://repo.anaconda.com/miniconda/Miniconda3-py311_23.11.0-2-Linux-x86_64.sh' \
    -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/miniconda3 \
    && rm /tmp/miniconda.sh

ENV PATH=/opt/miniconda3/bin:$PATH

RUN conda init --all && conda config --append channels conda-forge && \
    conda install -n base conda-libmamba-solver -y && \
    conda config --set solver libmamba

WORKDIR /testbed

ENTRYPOINT ["sleep", "infinity"]
