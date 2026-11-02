wsgi_app = "deployment.wsgi.wsgi:application"
bind = "127.0.0.1:8000"
workers = 1
user = "gen3"
group = "gen3"
timeout = 300
