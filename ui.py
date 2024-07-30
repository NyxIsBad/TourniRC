from flask import Flask, render_template, request, redirect, url_for
from waitress import serve

app = Flask(__name__)

@app.route('/')
def home():
    return "Welcome to the Home Page!"

@app.route('/example')
def example():
    return "This is an example route!"

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        # Handle form data here
        username = request.form['username']
        return redirect(url_for('show_user_profile', username=username))
    return '''
        <form method="post">
            Username: <input type="text" name="username"><br>
            <input type="submit" value="Submit">
        </form>
    '''

def debug_run():
    app.run()

def prod_run():
    serve(app=app, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    debug_run()