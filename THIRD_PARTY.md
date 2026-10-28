# Upstream components

- Osync: https://github.com/KORThomasJeong/Osync-p (MIT as documented upstream).
  Server files are copied from the public `thomasjeong/osync` image at the digest in the Dockerfile.
  The server source is not in that public plugin repository; no server source modification is included.
- PostgreSQL: https://www.postgresql.org/about/licence/ (PostgreSQL License).
- MinIO: https://github.com/minio/minio/tree/9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
  (GNU AGPLv3). Built without source changes. The image includes its license and a source archive
  with vendored Go dependencies under `/usr/share/osync/`. The Dockerfile contains the build recipe.
  Preserve these materials when distributing the image.

The source package supplied here contains packaging code only, not the upstream binaries.
