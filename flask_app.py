"""Point d'entree WSGI (PythonAnywhere pointe sur ce fichier)."""

from atelier import create_app

app = create_app()

if __name__ == "__main__":
    # utile en local uniquement
    app.run(host="0.0.0.0", port=5000, debug=True)
