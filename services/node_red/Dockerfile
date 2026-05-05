ARG NODE_RED_IMAGE_TAG=4.1.8-22
FROM nodered/node-red:${NODE_RED_IMAGE_TAG}

USER root
COPY generate-settings.cjs /usr/local/bin/generate-settings.cjs
COPY docker-entrypoint.sh /usr/local/bin/node-red-wrapper-entrypoint.sh
RUN chmod +x /usr/local/bin/node-red-wrapper-entrypoint.sh
USER node-red

ENTRYPOINT ["/usr/local/bin/node-red-wrapper-entrypoint.sh"]
CMD ["npm", "start", "--cache", "/data/.npm", "--", "--userDir", "/data"]
