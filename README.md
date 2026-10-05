# oro-network-map

Interactive network map with satellite and OpenStreetMap layers.

## Run locally

Serve the `dist` folder using a local HTTP server, for example:

```sh
python -m http.server 8000 --directory dist
```

Open http://localhost:8000.

The repository includes the network layers used by the map. `.openai/hosting.json` records the existing Sites hosting project.

## GitHub Pages

Pushes to `main` automatically deploy the `dist` directory through GitHub Actions. Enable GitHub Pages with GitHub Actions as the publishing source. For OROC, the optional `MAPBOX_PUBLIC_TOKEN` repository variable supplies the public Mapbox token; permit the Pages domain in its URL restrictions.
