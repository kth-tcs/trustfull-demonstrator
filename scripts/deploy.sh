#!/usr/bin/bash

docker build -t webdemo .

(
  cd auth
  docker build -t freja-auth .
)

cd ..
docker-compose up -d
