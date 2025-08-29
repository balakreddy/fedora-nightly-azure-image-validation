FROM registry.fedoraproject.org/fedora:42 as builder

RUN dnf install -y \
    git \
    python3-pip \
    python3-build \
    python3-hatchling

RUN mkdir -p /srv/fedora-cloud-testing
COPY . /srv/fedora-cloud-testing
RUN cd /srv/fedora-cloud-testing && hatchling build --target=wheel

RUN git clone https://github.com/microsoft/lisa.git /srv/lisa
WORKDIR /srv/lisa
RUN git checkout 20250819.1 && python -m build

FROM registry.fedoraproject.org/fedora:42

LABEL org.opencontainers.image.authors="Fedora Cloud SIG <cloud@lists.fedoraproject.org>"

RUN mkdir -p /srv/fedora-cloud-testing
WORKDIR /srv/fedora-cloud-testing

COPY --from=builder /srv/fedora-cloud-testing/dist /srv/fedora-cloud-testing/dist
COPY --from=builder /srv/lisa/dist/*whl /srv/fedora-cloud-testing/dist/
COPY --from=builder /srv/lisa/microsoft /srv/fedora-cloud-testing/microsoft
COPY --from=builder /srv/lisa/examples /srv/fedora-cloud-testing/examples

# Use the system-provided libraries as much as we can here.
#
# We do need to commit a small crime so the system-provided fedora-messaging
# library uses our virtualenv
RUN dnf install -y \
    python3-pip \
    fedora-messaging \
    python3-fedora-image-uploader-messages \
    python3-gobject \
    python3-paramiko \
    python3-pillow \
    python3-pyyaml \
    python3-retry \
    python3-requests
RUN python3 -m venv --system-site-packages venv && venv/bin/pip install --no-cache-dir dist/*
RUN cp /usr/bin/fedora-messaging /srv/fedora-cloud-testing/venv/bin/fedora-messaging && \
    sed -i 's|/usr/bin/python3|/srv/fedora-cloud-testing/venv/bin/python3|g' \
        /srv/fedora-cloud-testing/venv/bin/fedora-messaging

ENV PATH="/srv/fedora-cloud-testing/venv/bin:$PATH"
ENV VIRTUAL_ENV="/srv/fedora-cloud-testing/venv"

ENTRYPOINT ["/srv/fedora-cloud-testing/venv/bin/fedora-messaging"]
CMD ["consume"]
