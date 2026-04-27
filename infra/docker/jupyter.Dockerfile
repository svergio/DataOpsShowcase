FROM jupyter/datascience-notebook:python-3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

USER jovyan
