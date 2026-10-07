from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader
from docx import Document
import pandas as pd
import os

app = Flask(__name__)


# Count how many times the text appears
def count_occurrences(text, search_word):
    return text.lower().count(search_word.lower())


# Read PDF
def read_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()

        if extracted:
            text += extracted

    return text


# Read DOCX
def read_docx(file):
    document = Document(file)

    text = ""

    for paragraph in document.paragraphs:
        text += paragraph.text + " "

    return text


# Read Excel
def read_excel(file):
    excel = pd.ExcelFile(file)

    text = ""

    for sheet_name in excel.sheet_names:

        dataframe = pd.read_excel(
            file,
            sheet_name=sheet_name
        )

        text += dataframe.to_string()

    return text


# Main page
@app.route("/")
def home():
    return render_template("index.html")


# Search API
@app.route("/search", methods=["POST"])
def search():

    file = request.files.get("file")
    search_word = request.form.get("search_word")


    if not file:
        return jsonify({
            "message": "Please upload a file"
        })


    if not search_word:
        return jsonify({
            "message": "Please enter a word or text"
        })


    filename = file.filename.lower()


    try:

        # PDF
        if filename.endswith(".pdf"):

            text = read_pdf(file)


        # DOCX
        elif filename.endswith(".docx"):

            text = read_docx(file)


        # EXCEL
        elif (
            filename.endswith(".xlsx")
            or filename.endswith(".xls")
        ):

            text = read_excel(file)


        # TXT
        elif filename.endswith(".txt"):

            text = file.read().decode("utf-8")


        else:

            return jsonify({
                "message": "Unsupported file type"
            })


        # Count the word
        count = count_occurrences(
            text,
            search_word
        )


        if count > 0:

            return jsonify({
                "found": True,
                "count": count,
                "message":
                    f'"{search_word}" found {count} time(s)'
            })


        else:

            return jsonify({
                "found": False,
                "count": 0,
                "message":
                    f'"{search_word}" not found'
            })


    except Exception as error:

        return jsonify({
            "message": f"Error: {str(error)}"
        })


if __name__ == "__main__":
    app.run(
        debug=True
    )