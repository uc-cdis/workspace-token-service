import flask
import kubernetes

from .base import User


POD_USERNAME_ANNOTATION = 'gen3username'
JUPYTER_POD_ANNOTATION = 'hub.jupyter.org/username'


def get_username_from_ip(ip):
    # Fail if we can't load kubernetes config...
    try:
        kubernetes.config.load_incluster_config()
    except Exception:
        return None
    v1 = kubernetes.client.CoreV1Api()
    ret = v1.list_pod_for_all_namespaces(
        field_selector='status.podIP={}'.format(ip), watch=False)
    for pod in ret.items:
        if (pod.metadata.annotations
                and POD_USERNAME_ANNOTATION in pod.metadata.annotations):
            return pod.metadata.annotations[POD_USERNAME_ANNOTATION]
        elif (pod.metadata.annotations
                and JUPYTER_POD_ANNOTATION in pod.metadata.annotations):
            return pod.metadata.annotations[JUPYTER_POD_ANNOTATION]

    # No matching pod found
    return None


class K8SPlugin(object):
    def find_user(self):
        ip = flask.request.remote_addr
        username = get_username_from_ip(ip)
        return User(userid=username, username=username)
