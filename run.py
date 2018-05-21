from gen3meta.app import app
app.config['SQLALCHEMY_DATABASE_URI'] = (
   'postgresql://test:test@localhost:5432/gen3meta'
)
app.config['ENCRYPTION_KEY'] = 'asdfasdfs'
app.run('127.0.0.1', 5000, debug=True)
