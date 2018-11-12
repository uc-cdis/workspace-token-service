from wts.app import app
app.config['DEBUG'] = True
app.run('127.0.0.1', 5000, debug=True)
