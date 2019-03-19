from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired
from cape.client import CapeClient
from bs4 import BeautifulSoup
from cassandra.cluster import Cluster, NoHostAvailable
import json
import os
import requests

# Get cluser and deployment variables

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')

SECRET_KEY = app.config['SECRET_KEY']
API_BASE = str(os.getenv('API_BASE')) # Set in frontend-deployment.yaml
ADMIN_TOKEN = str(os.getenv('ADMIN_TOKEN')) # Set in frontend-deployment.yaml

cc = CapeClient(api_base=API_BASE, admin_token=ADMIN_TOKEN)

m_host = str(os.getenv('MERCURY_PARSER_SERVICE_HOST'))
m_port = str(os.getenv('MERCURY_PARSER_SERVICE_PORT'))
mercury_server = "http://{}:{}/".format(m_host, m_port)

cassandra_server = str(os.getenv('CASSANDRA_SERVICE_HOST'))

USER_TOKEN = 'token' # If not using 'token' during Cape setup, could set as a variable in frontend-deployment.yaml as with API_BASE etc.

# Connect to Cassandra database, create keyspaces and tables if they do not already exist

def cassandra_connect(cassandra_server):
    cluster = Cluster([cassandra_server])
    session = cluster.connect()
    try:
        session.execute("CREATE KEYSPACE webpage WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 2}")
        session.execute("CREATE TABLE webpage.documents (CapeID text PRIMARY KEY, URL text, Title text, Contents text)")
        session.execute("CREATE TABLE webpage.answers (ID text PRIMARY KEY, Question text, Answer text, Context text)")
    except:
        pass
    session = cluster.connect('webpage')
    return session

session = cassandra_connect(cassandra_server)

# Flask form for landing page

class QuestionForm(FlaskForm):
    url = StringField('Webpage url:') # Validator not set for url field (if no url provided, searches existing webpages)
    question = StringField('Question:', validators=[DataRequired()])
    submit = SubmitField('Submit')

# Pass urls to mercury-server and return text content

def get_parsed_text(url):
    resp = requests.post(mercury_server, data={'url': url})
    j_response = resp.json()
    content = j_response['content']
    title = j_response['title']
    xml = BeautifulSoup(content, "xml")
    text_out = []
    
    # mercury-server returns basic HTML content (having removed navigation and adds etc.) so we parse the html to extract
    # just the text content
    
    for i in xml.find_all('p'):
        text_out.append(i.text)
    all_text = "\n".join(text_out)
    return all_text, title

# Upload a parsed webpage to Cape and the Cassandra database

def upload_document(url, session):
    num_docs = session.execute("SELECT COUNT (*) from documents")
    i = num_docs.one().count
    parsed_text, parsed_title = get_parsed_text(url)
    new_document_id = cc.add_document(title=parsed_title, text=parsed_text, replace=True) # Set replace=True in case the app is
    # re-started and the database cleared (i.e. the document is in Cape but not in the database)
    session.execute("INSERT INTO documents (CapeID, URL, title, contents) VALUES (%s, %s, %s, %s)",
                    (new_document_id, url, parsed_title, parsed_text))

# Get an answer from Cape, return the answer and write it to the Cassandra database

def get_cape_answer(question, session):
    num_answers = session.execute("SELECT COUNT (*) from answers").one().count
    new_answer_id = "answer_" + str(num_answers)
    IDs = []
    for row in session.execute('SELECT CapeID FROM documents'):
        IDs.append(row.capeid) # Get the IDs from the documents table
    answer = cc.answer(question,
                       user_token=USER_TOKEN,
                       document_ids=IDs) # Search over all documents
    session.execute("INSERT INTO answers (ID, Question, Answer, Context) VALUES (%s, %s, %s, %s)",
                    (new_answer_id, question, answer[0]['answerText'], answer[0]['answerContext']))
    return answer

# Webapp landing page, a flask form where users can submit a url and question. 
# On submit, the form makes a POST request to /questions

@app.route('/')
def landing():
    form = QuestionForm()
    return render_template('landing.html', title='Ask a question!', form=form), 200

# Process urls and questions.

@app.route('/questions', methods=['GET', 'POST'])
def ask_a_question():
    form = QuestionForm()
    if form.validate_on_submit(): # Check to see if a question has been asked. If not return an error
        if form.url.data != "": # Check to see if a url has been submitted. 
            # If yes, check to see if it has been submitted previously
            urls = []
            for row in session.execute('SELECT URL from documents'):
                urls.append(row.url)
            if form.url.data not in urls: # If it has not been submitted previously, upload it
                upload_document(form.url.data, session)
            answer = get_cape_answer(form.question.data, session) # Get the answer and render output
            return render_template('question_response.html',
                                   title='Answer!',
                                   question=form.question.data,
                                   answer=answer[0]['answerText'],
                                   context=answer[0]['answerContext']), 201
        
        if form.url.data == "": # If no url specified, search current documents (if there are any)
            if session.execute("SELECT COUNT (*) from documents").one().count == 0:
                error = "You have no current documents. Specify a webpage to start." # If there are none, return an error
                return render_template('error.html', title='Error!', error=error), 400
            
            else:
                answer = get_cape_answer(form.question.data, session) # Get the answer from existing documents and render output
                return render_template('question_response.html',
                                       title='Answer!',
                                       question=form.question.data, 
                                       answer=answer[0]['answerText'],
                                       context=answer[0]['answerContext']), 201
            
    else:
        error = "You must ask a question."
        return render_template('error.html', title='Error!', error=error), 400

# Get a list of current documents
    
@app.route('/documents', methods=['GET'])
def get_documents():
    document_list = []
    for row in session.execute('SELECT * from documents'):
        entry = {}
        entry['title'] = row.title
        entry['content'] = row.contents
        document_list.append(entry)
    return render_template('document_list.html',
                           title="Documents!",
                           documents=document_list), 200

# Get a list of current answers

@app.route('/answers', methods=['GET'])
def get_answers():
    answer_list = []
    for row in session.execute('SELECT * from answers'):
        entry = {}
        entry['question'] = row.question
        entry['answer'] = row.answer
        entry['context'] = row.context
        answer_list.append(entry)
    return render_template('answer_list.html',
                           title="Answers!",
                           answers=answer_list), 200

if __name__=="__main__":
    app.run(host = '0.0.0.0', port=80, debug=False)
