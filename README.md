# Workspace Token Service
The reason we need this service is that a worker within a workspace is not tied to an active user web session, so there isn't a easy way for users within a worker to call Gen3 services other than manually copy the token into the worker.

Gen3 workspace token service acts as a OIDC client to acts on behalf of users to request refresh_token from fence. This will happens when user logins to a workspace from browser. WTS then stores the refresh token for that user, and exchange for to manage access_token and refresh_token for workers that belong to specific users in the workspace.
Each type of workspace environment should have a corresponding auth mechanism for the service to check the identity of a worker.
Currently has a k8s auth plugin that supports workers deployed as k8s pod with username annotation.

[architecture](https://raw.githubusercontent.com/uc-cdis/workspace-token-service/architecture.svg)

## how a workspace interacts with workspace token service
- workspace UI calls /oauth2/authorization_url to connect with fence during user login, this will do an OIDC dance with fence to obtain refresh_token if it's a new user or the user's previous refresh token is expired.
- worker calls /token?expires=seconds to get access token
