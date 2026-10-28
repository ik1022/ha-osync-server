# syntax=docker/dockerfile:1
FROM thomasjeong/osync@sha256:86f6bbf73350477a46b61a49bbfcca3a85dae23dfea079b370c7d321e3c76918 AS osync

# MinIO's final security release is source-only; do not use the removed Hub image.
FROM golang@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59 AS minio
RUN apk add --no-cache git ca-certificates
WORKDIR /src/minio
RUN git init . \
    && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth=1 origin 9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a \
    && git checkout --detach FETCH_HEAD \
    && go mod vendor \
    && CGO_ENABLED=0 go build -mod=vendor -trimpath -o /out/minio . \
    && tar --exclude=.git -czf /out/minio-source.tar.gz .

FROM postgres@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
ARG BUILD_VERSION=0.1.0
ARG BUILD_ARCH
LABEL io.hass.type="app" io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}"
RUN apk add --no-cache python3 ca-certificates libstdc++ libgcc su-exec \
    && addgroup -S osync && adduser -S -G osync osync \
    && addgroup -S minio && adduser -S -G minio minio
COPY --from=osync /app /app
COPY --from=minio /out/minio /usr/local/bin/minio
COPY --from=minio /out/minio-source.tar.gz /usr/share/osync/minio-source.tar.gz
COPY --from=minio /src/minio/LICENSE /usr/share/osync/MINIO-LICENSE
COPY runtime.py /opt/osync/runtime.py
WORKDIR /app
ENV NODE_ENV=production
EXPOSE 3000 9000
ENTRYPOINT ["python3", "-u", "/opt/osync/runtime.py"]
CMD []
