import subprocess
import tempfile
import os
from flask import Flask, request, render_template, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PNGDB Web Interface</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
        .output-box {
            white-space: pre-wrap;       /* CSS 3 */
            white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
            white-space: -pre-wrap;      /* Opera 4-6 */
            white-space: -o-pre-wrap;    /* Opera 7 */
            word-wrap: break-word;       /* Internet Explorer 5.5+ */
        }
    </style>
</head>
<body class="bg-gray-100 text-gray-800">
    <div class="container mx-auto p-4 sm:p-6 md:p-8 max-w-2xl">
        <div class="bg-white shadow-lg rounded-2xl p-6 md:p-8">
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">PNGDB Web Interface</h1>
            <p class="text-gray-600 mb-6">Enter your credentials and a command to run on the database.</p>

            <form method="post">
                <div class="space-y-4">
                    <div>
                        <label for="username" class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                        <input type="text" id="username" name="username" required
                               class="w-full px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-200"
                               placeholder="e.g., db_user">
                    </div>

                    <div>
                        <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                        <input type="password" id="password" name="password" required
                               class="w-full px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-200"
                               placeholder="Your database password">
                    </div>

                    <div>
                        <label for="command" class="block text-sm font-medium text-gray-700 mb-1">Database Command</label>
                        <textarea id="command" name="command" rows="6" required
                                  class="w-full px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-200"
                                  placeholder="Enter your database command here..."></textarea>
                    </div>
                </div>

                <div class="mt-6">
                    <button type="submit"
                            class="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 transition duration-300 ease-in-out">
                        Execute Command
                    </button>
                </div>
            </form>

            {% if output is not none %}
            <div class="mt-8">
                <h2 class="text-xl font-semibold text-gray-900 mb-3">Database Output</h2>
                <div class="bg-gray-900 text-white font-mono text-sm p-4 rounded-lg output-box">
                    {{ output }}
                </div>
            </div>
            {% endif %}

        </div>
        <footer class="text-center mt-6 text-sm text-gray-500">
            <p>Python & Flask DB Connector</p>
        </footer>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Handles both displaying the form (GET) and processing the command (POST).
    """
    output_message = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        command_text = request.form.get('command')

        if not all([username, password, command_text]):
            output_message = "Error: Username, password, and command cannot be empty."
            return render_template_string(HTML_TEMPLATE, output=output_message)

        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".pngdb", encoding='utf-8') as temp_command_file:
                temp_command_filename = temp_command_file.name
                temp_command_file.write(command_text)
                temp_command_file.flush()

            db_filename = f"{username}.png"
            
            command_to_run = [
                'python',
                'pngdb.py',
                temp_command_filename,
                db_filename,
                password
            ]

            process = subprocess.run(
                command_to_run,
                capture_output=True,
                text=True,
                check=False
            )

            if process.stdout:
                output_message = f"--- SUCCESS ---\n{process.stdout}"
            if process.stderr:
                error_details = f"--- ERROR ---\n{process.stderr}"
                output_message = f"{output_message}\n{error_details}" if output_message else error_details

            if not output_message:
                output_message = "Script executed but produced no output."

        except FileNotFoundError:
            output_message = "Error: 'python' or 'pngdb.py' not found. Make sure Python is installed and pngdb.py is in the same directory as app.py."
        except Exception as e:
            output_message = f"An unexpected error occurred: {e}"
        finally:
            if 'temp_command_filename' in locals() and os.path.exists(temp_command_filename):
                os.remove(temp_command_filename)

    return render_template_string(HTML_TEMPLATE, output=output_message)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
