# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=docker.io/library/python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
ARG TAKSERVER_IMAGE=ghcr.io/pvarki/tak-server:5.8.69-260913-slimignite-pr136@sha256:5d250adfdb835e9bfafcce294736041d4fbd32c1ffde7b803f17e28bf2f85a09

FROM ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 AS uv
FROM docker.io/library/eclipse-temurin:17-jdk-noble@sha256:fb79620c3f6ee8f1c7530a8dc4fd49e3b410bcef037694ad4858a1553bac4170 AS jdk
FROM docker.io/library/eclipse-temurin:17-jre-noble@sha256:900322f4cc1b9da9d730ae4bb56d8a1dabbaa9cfa32809fc8b542b600370a045 AS jre
FROM ${TAKSERVER_IMAGE} AS tak

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM build AS api-test
COPY tests ./tests
COPY docs/package-api.openapi.json ./docs/package-api.openapi.json
RUN uv sync --locked --no-editable
CMD ["/opt/venv/bin/python", "-m", "pytest"]

FROM api-test AS package-test
COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk PATH="/opt/java/openjdk/bin:$PATH"
CMD ["/opt/venv/bin/python", "-m", "pytest", "--require-keytool"]

FROM build AS operator-build
COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk PATH="/opt/java/openjdk/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
RUN uv sync --locked --no-dev --no-editable --extra operator

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN /usr/local/bin/python -m pip uninstall -y pip
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
USER 10001:10001
ENTRYPOINT ["opendefence-integration-tak"]
CMD ["--help"]

FROM runtime AS api

FROM runtime AS operator
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=jre /opt/java/openjdk /opt/java/openjdk
COPY --from=operator-build /opt/venv /opt/venv
COPY --from=tak /opt/tak/utils/UserManager.jar /opt/tak/utils/UserManager.jar
COPY --from=tak /opt/tak/version.txt /opt/tak/version.txt
ENV JAVA_HOME=/opt/java/openjdk PATH="/opt/java/openjdk/bin:$PATH"
USER 10001:10001
