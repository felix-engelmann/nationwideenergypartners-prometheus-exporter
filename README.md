# NEP Prometheus Exporter

A lightweight Prometheus exporter that fetches WATER and ELECTRIC usage from the NEP API using Cognito authentication. Designed to run as a service, exposing metrics on /metrics.

## Features

* Logs in with USERNAME and PASSWORD via AWS Cognito (SRP)
* Fetches the first premiseId on startup

## Usage

The easiest is the docker compose file, to configure, set your username and password as environment variables.
