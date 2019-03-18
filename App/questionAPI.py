# SET UP STEPS
# Launch mercury server (node index.js in the express_app folder)
# mercury runs on local host 8080
# UPDATE: uploaded mercury as a git repository. Add readme... packaged with docker and can deploy on a micro server. To work out ports. Think 8080 should be for local. So serve on 80?
# Launch cape server (GCP -> cape experiment -> VM instance from template (cape-vm))
# Wait for container to be built... (a few minutes)
# View VM logs. Get api base and add to this file.
# SSH to VM and...
# run a test QA: curl 'http://localhost:5050/api/0.1/answer?token=demo&question=Who+heads+the+board?&text=The+board+is+represented+by+the+chairman'
# run: curl -v "http://localhost:5050/api/0.1/user/create-user?userId=user_1&password=password&token=token&superAdminToken=REPLACEME"
# This sets up a new user with token "token", already hardcoded in this file
# run: curl -v "http://localhost:5050/api/0.1/user/login?login=user_1&password=password"
# This logs user_1 in and returns an ADMIN TOKEN. Add the admin token to this file.
# Run this server with python questionAPI.py
# Runs on local host 5000

# There's a whole login thing here: https://developers.google.com/api-client-library/python/auth/web-app

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

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')

SECRET_KEY = app.config['SECRET_KEY']
API_BASE = str(os.getenv('API_BASE'))
ADMIN_TOKEN = str(os.getenv('ADMIN_TOKEN'))

cc = CapeClient(api_base=API_BASE, admin_token=ADMIN_TOKEN)

m_host = str(os.getenv('MERCURY_PARSER_SERVICE_HOST'))
m_port = str(os.getenv('MERCURY_PARSER_SERVICE_PORT'))
mercury_server = "http://{}:{}/".format(m_host, m_port)

cassandra_server = str(os.getenv('CASSANDRA_TOKEN'))

#str(os.getenv('CASSANDRA_SERVICE_HOST'))

USER_TOKEN = 'token'

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

class QuestionForm(FlaskForm):
    url = StringField('Webpage url:')
    question = StringField('Question:', validators=[DataRequired()])
    submit = SubmitField('Submit')

def get_parsed_text(url): # Mercury parse of specified url
    resp = requests.post(mercury_server, data={'url': url})
    j_response = resp.json()
    content = j_response['content']
    title = j_response['title']
    xml = BeautifulSoup(content, "xml")
    text_out = []
    for i in xml.find_all('p'):
        text_out.append(i.text)
    all_text = "\n".join(text_out)
    return all_text, title

def upload_document(url, session): # Upload parsed webpage to cape
    num_docs = session.execute("SELECT COUNT (*) from documents") # querey documents table to get number (things that's just count)
    i = num_docs.one().count
    parsed_text, parsed_title = get_parsed_text(url)
    new_document_id = cc.add_document(title=parsed_title, text=parsed_text, replace=True) # If the front end is
    # re-loaded and the url list cleared, then whilst docs might persist in cape, we have not record of them. Set
    # replace = True to avoid error on trying to write new documents that have been persisted in cape.
    session.execute("INSERT INTO documents (CapeID, URL, title, contents) VALUES (%s, %s, %s, %s)",
                    (new_document_id, url, parsed_title, parsed_text))
    
def get_cape_answer(question, session): # Get answer from cape
    num_answers = session.execute("SELECT COUNT (*) from answers").one().count # count answers in answers table
    new_answer_id = "answer_" + str(num_answers)
    IDs = []
    for row in session.execute('SELECT CapeID FROM documents'):
        IDs.append(row.capeid) # get the IDs from the documents table
    answer = cc.answer(question,
                       user_token=USER_TOKEN,
                       document_ids=IDs) # Search over all documents
    session.execute("INSERT INTO answers (ID, Question, Answer, Context) VALUES (%s, %s, %s, %s)",
                    (new_answer_id, question, answer[0]['answerText'], answer[0]['answerContext']))
    return answer

@app.route('/') # Question page
def landing():
    form = QuestionForm()
    return render_template('landing.html', title='Ask a question!', form=form)

@app.route('/questions', methods=['GET', 'POST'])
def ask_a_question():
    form = QuestionForm()
    if form.validate_on_submit(): # Check to see if a question has been asked
        if form.url.data != "": # If a url is specified, check repeat and then parse
            urls = []
            for row in session.execute('SELECT URL from documents'):
                urls.append(row.url)
            if form.url.data not in urls:
                upload_document(form.url.data, session)
            answer = get_cape_answer(form.question.data, session)
            return render_template('question_response.html',
                                   title='Answer!',
                                   question=form.question.data,
                                   answer=answer[0]['answerText'],
                                   context=answer[0]['answerContext']), 201
        if form.url.data == "": # If no url specified, search current documents (if there are any)
            if session.execute("SELECT COUNT (*) from documents").one().count == 0:
                error = "You have no current documents. Specify a webpage to start."
                return render_template('error.html', title='Error!', error=error), 400
            else:
                answer = get_cape_answer(form.question.data, session)
                return render_template('question_response.html',
                                       title='Answer!',
                                       question=form.question.data, 
                                       answer=answer[0]['answerText'],
                                       context=answer[0]['answerContext']), 201
    else:
        error = "You must ask a question."
        return render_template('error.html', title='Error!', error=error), 400
    
@app.route('/documents', methods=['GET'])
def get_documents():
    document_list = []
    for row in session.execute('SELECT * from documents'):
        entry = {}
        entry['title'] = row.title
        entry['content'] = row.contents
        document_list.append(entry) # querey documents table and get a list of contents
    return render_template('document_list.html',
                           title="Documents!",
                           documents=document_list), 201

@app.route('/answers', methods=['GET'])
def get_answers():
    answer_list = []
    for row in session.execute('SELECT * from answers'):
        entry = {}
        entry['question'] = row.question
        entry['answer'] = row.answer
        entry['context'] = row.context
        answer_list.append(entry) # query answer table and get a list of answers
    return render_template('answer_list.html',
                           title="Answers!",
                           answers=answer_list), 201

if __name__=="__main__":
    app.run(host = '0.0.0.0', port=80, debug=False)
