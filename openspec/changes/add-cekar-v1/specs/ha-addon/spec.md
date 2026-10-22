## ADDED Requirements

### Requirement: Add-on repository
The project repository SHALL be installable as a Home Assistant add-on repository. It SHALL contain a root `repository.yaml` and an add-on folder `addon/cekar/` with `config.yaml`, `Dockerfile`, `DOCS.md`, `CHANGELOG.md`, `icon.png` and `logo.png`.

#### Scenario: Add repository in HA
- **WHEN** the user adds the repository URL in the HA add-on store
- **THEN** the cekar add-on is listed and can be installed

### Requirement: Ingress panel for every household user
The add-on SHALL enable Ingress on port 8099 and add a sidebar panel titled "Cekar" with a basket icon (`mdi:basket`). The panel SHALL NOT be restricted to administrators (`panel_admin: false`). The add-on SHALL support at least the `amd64` and `aarch64` architectures.

#### Scenario: Open from sidebar
- **WHEN** the installed add-on is started and a household user clicks the sidebar panel
- **THEN** cekar opens inside Home Assistant on that user's last opened list

#### Scenario: Non-admin user
- **WHEN** an HA user without administrator rights opens the sidebar
- **THEN** the Cekar panel is shown and usable

### Requirement: No second header inside Home Assistant
In add-on mode on a phone-sized screen the system SHALL NOT show its own top bar, since Home Assistant shows one; the bottom navigation stays. The signed-in person and, where it applies, the "switch person" action SHALL then be reachable in Settings. Standalone mode and wide screens keep the app bar with the user menu.

#### Scenario: Phone inside Home Assistant
- **WHEN** a user opens the panel on a phone
- **THEN** only Home Assistant's header is shown above the content, and Settings shows who is signed in

### Requirement: Optional API port
The add-on `config.yaml` SHALL declare the API port `8100/tcp` under `ports` with the host port `null` (off by default) and describe it under `ports_description`. The `api_token` option SHALL be optional and a password-type field, and SHALL be the only add-on option in v1. The add-on SHALL NOT request `homeassistant_api` in v1. DOCS.md SHALL explain how to enable the port and the token.

#### Scenario: Default install exposes nothing
- **WHEN** the add-on is installed with default settings
- **THEN** no host port is mapped and only Ingress can reach the app

#### Scenario: User enables the API
- **WHEN** the user sets `api_token` (16 characters or more) and a host port for `8100/tcp` and restarts the add-on
- **THEN** `GET http://<ha-host>:<host-port>/api/v1/health` with the Bearer header returns 200

### Requirement: Persistent data and backups
The add-on SHALL store its SQLite database (`cekar.db`) and generated secrets under `/data`, so that they survive restarts and upgrades and are included in Home Assistant backups. On startup it SHALL apply pending schema migrations automatically.

#### Scenario: Upgrade keeps data
- **WHEN** the add-on is upgraded to a version with a new schema migration
- **THEN** existing lists, items, expenses and payments are preserved and the migration is applied at startup

### Requirement: Standalone image from the same build
The same container image SHALL run outside Home Assistant when started in standalone mode. It SHALL listen on port 8080 and store data in a mounted `/data` volume.

#### Scenario: docker run
- **WHEN** a user runs the image with `-p 8080:8080 -v ./data:/data` in standalone mode
- **THEN** the app is reachable at `http://host:8080/`
- **AND** the data persists in `./data`
