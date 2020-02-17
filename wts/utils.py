import flask


def get_oauth_client(idp=None):
    """
    Args:
        idp (str, optional): IDP for the OAuthClient to return. If not
        provided, will use the IDP provided as a request argument. By default,
        will return the default OAuthClient.

    Returns:
        (OAuthClient, str) tuple
    """
    idp = idp or flask.request.args.get("idp", "default")
    flask.current_app.logger.info("get_oauth_client idp={}".format(idp))
    try:
        client = flask.current_app.oauth2_clients[idp]
    except KeyError:
        flask.current_app.logger.exception('Requested IDP "{}" is not configured')
        raise
    return client, idp
