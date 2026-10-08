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

## Integrated OLT workspace

Rețea, OLT / porturi and Unelte share one Leaflet map. Each repository retains its own network manifest and layers. The OLT directory and per-site data are copied from the OLT ORO dataset into `dist/olt`; no spreadsheet or NCE session data is published. ODB selection is independent of DP selection. Network site search popups can open the OLT workspace.

Desktop uses a fixed side panel; mobile uses a collapsible bottom panel. DOWN status is selected manually. No alarm API, NCE agent, HAR session or local alarm connection is enabled in these combined applications. The standalone OLT ORO application is unchanged.

Ports expand to show individually selectable ODBs. Port point visibility, manual DOWN status and ODB selection work without enabling all points for an OLT. OROC uses JS (joncțiune splitată) for level-1 points; original source aliases remain intact.
