# Workspace Token Service (WTS)

The reason we need this service is that a worker within a workspace is not tied to an active user web session, so there isn't an easy way for users within a worker to call Gen3 services other than manually copying the token into the worker.

The Gen3 workspace token service acts as an OIDC client which acts on behalf of users to request refresh tokens from [Fence](https://github.com/uc-cdis/fence). This happens when a user logs into a workspace from the browser. WTS then stores the refresh token for that user, and manages access tokens and refresh tokens for workers that belong to specific users in the workspace.

Each type of workspace environment should have a corresponding auth mechanism for the service to check the identity of a worker. Currently WTS has a K8s auth plugin that supports workers deployed as K8s pods with username annotation.

OpenAPI Specification [here](http://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/workspace-token-service/master/openapi/swagger.yaml).


## How a workspace interacts with WTS

- The workspace UI calls `/oauth2/authorization_url` to connect with Fence during user login, this will do an OIDC dance with fence to obtain a refresh token if it's a new user or if the user's previous refresh token is expired.
- The worker calls `/token?expires=seconds` to get an access token


## Why isn't WTS part of Fence?

The `/token` endpoint is [dependent on the local Kubernetes](https://github.com/uc-cdis/workspace-token-service/blob/master/wts/auth_plugins/k8s.py). It trusts the caller ([Gen3Fuse](https://github.com/uc-cdis/gen3-fuse)) to pass the correct user identity.

<img src="docs/img/architecture.svg">


## Gen3 Workspace architecture

[![](docs/img/Export_to_WS_Architecture_Flow.png)](https://www.lucidchart.com/documents/edit/e844ca6b-fb75-460c-8a8e-5ddb4a17b8d9/0_0)
