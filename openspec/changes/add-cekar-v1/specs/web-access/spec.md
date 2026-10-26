## ADDED Requirements

### Requirement: Serve under a path prefix or at root
The system SHALL generate every link, form action, static-asset URL and fetch URL relative to a base path. The base path SHALL be taken from the `X-Ingress-Path` request header when present, otherwise from the `BASE_PATH` setting, otherwise `/`.

#### Scenario: Ingress prefix
- **WHEN** a request arrives with `X-Ingress-Path: /api/hassio_ingress/abc123`
- **THEN** all URLs in the returned page start with `/api/hassio_ingress/abc123/`

#### Scenario: Root
- **WHEN** no prefix header or setting is present
- **THEN** all URLs start with `/`

### Requirement: Add-on mode access control
In add-on mode, the system SHALL NOT show a login. The Ingress listener SHALL accept HTTP requests only from the Home Assistant Supervisor ingress proxy, and SHALL reject requests from other source addresses with HTTP 403.

#### Scenario: Direct access rejected
- **WHEN** in add-on mode a request arrives from an address other than the ingress proxy
- **THEN** the response is 403

#### Scenario: Forged identity headers from elsewhere
- **WHEN** in add-on mode a request with `X-Remote-User-Id` arrives from an address other than the ingress proxy
- **THEN** the response is 403 and no user is registered

### Requirement: Optional add-on API listener
In add-on mode, the system SHALL run a second listener on container port 8100 only when `api_token` is set and non-empty. That listener SHALL serve only paths under `/api/v1`, SHALL require `Authorization: Bearer <api_token>` compared in constant time, and SHALL answer every other path with HTTP 404. A token shorter than 16 characters SHALL make startup fail with an error message. Without `api_token` the listener SHALL NOT start and a warning SHALL be logged. In v1 the only endpoint SHALL be `GET /api/v1/health`. The identity rules SHALL NOT apply on this listener (it acts as no person and cannot write).

#### Scenario: Token required
- **WHEN** a request to `/api/v1/health` on the API listener has no `Authorization` header
- **THEN** the response is 401 with `WWW-Authenticate: Bearer`

#### Scenario: Only the API is served
- **WHEN** a request for `/` or `/static/app.css` arrives on the API listener, with or without a valid token
- **THEN** the response is 404

#### Scenario: No token, no listener
- **WHEN** the add-on starts without `api_token`
- **THEN** the API listener is not started
- **AND** a warning is logged

#### Scenario: Short token
- **WHEN** the add-on starts with an `api_token` of fewer than 16 characters
- **THEN** startup fails with an error message and no listener starts

### Requirement: Identity from Ingress user headers
In add-on mode, the system SHALL identify the acting person from the `X-Remote-User-Id` request header, and SHALL take the user name and display name from `X-Remote-User-Name` and `X-Remote-User-Display-Name`. When these headers are present they SHALL take precedence over any identity cookie.

#### Scenario: Known HA user
- **WHEN** a proxied request carries `X-Remote-User-Id` of a registered user
- **THEN** the page is rendered for that user
- **AND** new items and expenses default to that user as adder or payer

#### Scenario: Header wins over cookie
- **WHEN** a proxied request carries `X-Remote-User-Id` of user A and an identity cookie naming user B
- **THEN** the request is handled as user A

### Requirement: Identity picker fallback
When no identity header is present (in add-on mode) and always in standalone mode, the system SHALL identify the acting person by a signed identity cookie. Without a valid cookie it SHALL show a "Who are you?" page listing the known people, with a field to add a new person by name, and SHALL set the cookie (valid one year) on choice. A "Switch person" action SHALL clear the cookie.

#### Scenario: First visit without headers
- **WHEN** a request without identity headers and without an identity cookie arrives
- **THEN** the "Who are you?" page is shown
- **AND** after choosing a person, the app opens as that person on later visits from that browser

#### Scenario: Tampered cookie
- **WHEN** the identity cookie's signature does not verify
- **THEN** it is ignored and the "Who are you?" page is shown

#### Scenario: Switch person
- **WHEN** the user chooses "Switch person"
- **THEN** the identity cookie is cleared and the "Who are you?" page is shown

### Requirement: Optional standalone login
In standalone mode, when `CEKAR_PASSWORD` is set, the system SHALL require a login with that password before serving any page, and SHALL keep the session in a signed cookie. When `CEKAR_API_TOKEN` or `CEKAR_PASSWORD` is set, `/api/v1` SHALL accept only that Bearer token or a valid login session. When no password is set, the system SHALL serve without login and SHALL log a warning at startup. The login SHALL come before the identity picker.

#### Scenario: Login required
- **WHEN** a password is configured and an unauthenticated user opens any page
- **THEN** the user is redirected to the login page

#### Scenario: Wrong password
- **WHEN** the user submits a wrong password
- **THEN** access is denied
- **AND** no session cookie is issued

### Requirement: No external network dependencies
Pages SHALL load without internet access. All scripts, styles, icons and fonts SHALL be served by the app itself.

#### Scenario: Offline page load
- **WHEN** any page is rendered
- **THEN** it references no external hosts
- **AND** the only exceptions are the GitHub and documentation links at the bottom of Settings, which open in a new tab and load nothing into the page
