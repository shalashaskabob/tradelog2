from app import create_app, models

app = create_app()

if __name__ == '__main__':
    app.run(debug=True) 