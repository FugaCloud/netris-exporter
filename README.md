# netris-exporter
Scrape the Netris API for metrics.

## Build and Deploy

To build the image:

```bash
docker build -t fugacloud/netris-exporter .
```

Create a config file and modify it to reflect your environment.

```bash
cp config.yaml.example config.yaml
vi config.yaml
```

And start the container:

```bash
docker compose up -d
```

Test it out:

```bash
curl localhost:3000
```
