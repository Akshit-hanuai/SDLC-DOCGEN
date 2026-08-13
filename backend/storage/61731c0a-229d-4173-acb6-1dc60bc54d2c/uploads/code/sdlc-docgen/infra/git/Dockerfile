FROM alpine:3.20

RUN apk add --no-cache git git-daemon

COPY init-repos.sh /init-repos.sh
RUN chmod +x /init-repos.sh

EXPOSE 9418
ENTRYPOINT ["/init-repos.sh"]
