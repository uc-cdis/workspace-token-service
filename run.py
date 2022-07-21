from wts.api import app, setup_app

if __name__ == "__main__":
    setup_app(app)
    app.run(debug=True)
